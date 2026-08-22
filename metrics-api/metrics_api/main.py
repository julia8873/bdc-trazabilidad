from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import requests
import jwt
import datetime
import secrets
import hashlib
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Query, status, Response, Request

from metrics_api.db import get_session
from metrics_api.auth import verify_token, AuthenticatedUser, verificar_permisos, JWT_SECRET_KEY, JWT_ALGORITHM
from metrics_api.schemas import (
    CourseMetricsResponse,
    StudentMetricsResponse,
    PaginatedInteractions,
    CourseStudentsResponse,
    StudentCourseItem,
    AgentSummaryResponse,
    AgentFollowUpRequest,
    AgentFollowUpResponse
)
from metrics_api.repository import (
    get_course_aggregates,
    get_student_aggregates,
    get_interacciones_by_curso,
    get_interacciones_by_alumno,
    get_schema_version
)
from metrics_api.models import AuditoriaAcceso, RefreshToken

class LoginRequest(BaseModel):
    """
    Modelo para la peticion de login.
    """
    username: str
    password: str

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("MOODLE_AUTH_URL"):
        raise RuntimeError("FATAL: MOODLE_AUTH_URL no está configurado.")
    if not os.getenv("MAPEO_API_URL"):
        raise RuntimeError("FATAL: MAPEO_API_URL no está configurado.")
    if not os.getenv("MAPEO_API_TOKEN") or os.getenv("MAPEO_API_TOKEN") in ("default_token", "changeme"):
        raise RuntimeError("FATAL: MAPEO_API_TOKEN no está configurado correctamente.")
    from metrics_api.auth import JWT_SECRET_KEY
    if not JWT_SECRET_KEY or JWT_SECRET_KEY in ("default_token", "changeme_in_production"):
        raise RuntimeError("FATAL: JWT_SECRET_KEY no está configurado de manera segura.")
    yield

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class SunsetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        if route and getattr(route, "deprecated", False):
            response.headers["Sunset"] = "Wed, 01 Jan 2027 00:00:00 GMT"
        return response

app = FastAPI(
    title="Metrics API",
    description="API para exponer métricas agregadas de interacciones (Fase 4)",
    lifespan=lifespan,
    root_path="/api",
    docs_url="/docs" if os.getenv("ENVIRONMENT") in ["dev", "local"] else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") in ["dev", "local"] else None,
    openapi_url="/openapi.json" if os.getenv("ENVIRONMENT") in ["dev", "local"] else None
)
app.add_middleware(SunsetMiddleware)

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"type": "about:blank", "title": "HTTP Error", "status": exc.status_code, "detail": str(exc.detail), "instance": request.url.path}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"type": "about:blank", "title": "Validation Error", "status": 422, "detail": str(exc.errors()), "instance": request.url.path}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"type": "about:blank", "title": "Internal Server Error", "status": 500, "detail": "Ocurrió un error inesperado", "instance": request.url.path}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/v1/health", status_code=status.HTTP_200_OK)
@app.get("/health", status_code=status.HTTP_200_OK, deprecated=True)
def health_check(response: Response, request: Request, session: Session = Depends(get_session)):
    if not request.url.path.startswith("/v1/"):
        response.headers["Sunset"] = "Wed, 18 Feb 2027 00:00:00 GMT"

    version = get_schema_version(session)
    return {"status": "ok", "schema_version": version}

@app.get("/v1/metrics/cursos/{curso_id}", response_model=CourseMetricsResponse)
def get_course_metrics(response: Response, request: Request, 
    curso_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):

    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden ver métricas del curso completo")
    total, by_type, percentiles = get_course_aggregates(session, curso_id)
    return CourseMetricsResponse(
        course_id=curso_id,
        total_interactions=total,
        interactions_by_type=by_type,
        percentiles=percentiles
    )

@app.get("/v1/metrics/cursos/{curso_id}/interacciones", response_model=PaginatedInteractions)
def get_course_interactions(response: Response, request: Request, 
    curso_id: int,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden ver interacciones del curso")
    items, total = get_interacciones_by_curso(session, curso_id, limit=limit, offset=offset)
    return PaginatedInteractions(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes", response_model=CourseStudentsResponse)
def get_course_students(response: Response, request: Request, 
    curso_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verify_token)
):
    if not request.url.path.startswith("/v1/"):
        response.headers["Sunset"] = "Wed, 18 Feb 2027 00:00:00 GMT"

    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden ver la lista de alumnos")
    
    if curso_id not in user.allowed_courses:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver los alumnos de este curso")
    
    # 1. Fetch students from mapeo-api
    mapeo_url = os.getenv("MAPEO_API_URL")
    mapeo_token = os.getenv("MAPEO_API_TOKEN")
    
    try:
        headers = {}
        if mapeo_token:
            headers["Authorization"] = f"Bearer {mapeo_token}"
        m_api_res = requests.get(
            f"{mapeo_url}/mapeos?moodle_course_id={curso_id}",
            headers=headers,
            timeout=5
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Mapeo API no disponible")
    
    if m_api_res.status_code != 200:
        if m_api_res.status_code == 404:
            return CourseStudentsResponse(course_id=curso_id, students=[])
        raise HTTPException(status_code=503, detail="Error consultando alumnos del curso")

    mapeos = m_api_res.json()
    
    students_list = []
    from metrics_api.models import Interaccion, DiscrepanciaAuditoria
    from sqlalchemy import func
    
    for m in mapeos:
        if m.get("is_teacher"):
            continue # Skip teachers
            
        student_id = m.get("moodle_user_id")
        
        # 2. Get metrics for this student
        total_interactions, _ = get_student_aggregates(session, student_id, curso_id)
        
        # 3. Get last activity timestamp
        last_activity = session.query(func.max(Interaccion.timestamp)).filter(
            Interaccion.moodle_user_id == student_id,
            Interaccion.moodle_course_id == curso_id
        ).scalar()
        
        # 4. Check for discrepancies
        has_discrepancies = session.query(DiscrepanciaAuditoria).filter(
            DiscrepanciaAuditoria.moodle_user_id == student_id,
            DiscrepanciaAuditoria.moodle_course_id == curso_id
        ).first() is not None
        
        students_list.append(StudentCourseItem(
            moodle_user_id=student_id,
            moodle_username=m.get("moodle_username") or f"user_{student_id}",
            repo_url=m.get("repo_url"),
            total_interactions=total_interactions,
            ultima_actividad=last_activity,
            estado_sincronizacion="DISCREPANCIAS_PENDIENTES" if has_discrepancies else "OK"
        ))
        
    return CourseStudentsResponse(
        course_id=curso_id,
        students=students_list
    )

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes/{estudiante_id}", response_model=StudentMetricsResponse)
def get_student_metrics(response: Response, request: Request, 
    curso_id: int, estudiante_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):

    if not user.is_teacher and user.moodle_user_id != estudiante_id:
        raise HTTPException(status_code=403, detail="No puedes ver las métricas de otro alumno")
    # Verificamos si el alumno tiene actividad en general para retornar 404 o 200 con total=0
    # Como la regla dice "200 con total_interactions: 0 no 404", lo retornamos directamente.
    total, by_type = get_student_aggregates(session, estudiante_id, curso_id)
    
    return StudentMetricsResponse(
        student_id=estudiante_id,
        course_id=curso_id,
        total_interactions=total,
        interactions_by_type=by_type
    )

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes/{estudiante_id}/interacciones", response_model=PaginatedInteractions)
def get_student_interactions(response: Response, request: Request, 
    curso_id: int, estudiante_id: int,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):

    if not user.is_teacher and user.moodle_user_id != estudiante_id:
        raise HTTPException(status_code=403, detail="No puedes ver las métricas de otro alumno")
    items, total = get_interacciones_by_alumno(session, estudiante_id, curso_id, limit=limit, offset=offset)
    return PaginatedInteractions(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )

@app.post("/v1/token")
@app.post("/token", deprecated=True)
def login(request: LoginRequest, response: Response, session: Session = Depends(get_session)):

    moodle_url = os.getenv("MOODLE_AUTH_URL")
    mapeo_url = os.getenv("MAPEO_API_URL")

    # 1. Autenticar en Moodle
    moodle_authenticated = False
    moodle_error = False
    try:
        m_res = requests.post(
            moodle_url, 
            headers={"Host": "localhost:8000"}, # Host esperado por defecto en el dev local
            data={"username": request.username, "password": request.password, "service": "moodle_mobile_app"},
            timeout=5
        )
        if m_res.status_code == 200:
            m_data = m_res.json()
            if "token" in m_data:
                moodle_authenticated = True
                moodle_error = False
        elif m_res.status_code == 401:
            moodle_error = False
        else:
            moodle_error = True
    except requests.RequestException:
        moodle_error = True
    
    # Fallback para pruebas de interfaz si Moodle no tiene Web Services o está caído
    if not moodle_authenticated and os.getenv("ENABLE_DEMO_AUTH", "false").lower() == "true":
        if (request.username == "admin" and request.password in ("testpass", "admin")) or \
           (request.username == "profesor1" and request.password == "Profesor1!") or \
           (request.username == "alumno1" and request.password == "Alumno1!") or \
           (request.username == "alumno" and request.password == "alumno"):
            moodle_authenticated = True
            moodle_error = False # Se superó la prueba con el mock
            
    if not moodle_authenticated:
        if moodle_error:
            raise HTTPException(status_code=503, detail="Moodle no disponible")
        
        auditoria = AuditoriaAcceso(
            moodle_username=request.username,
            recurso="/token",
            resultado="FAILED_MOODLE_AUTH",
            metadatos={"detail": "Credenciales inválidas en Moodle"}
        )
        session.add(auditoria)
        session.commit()
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # 2. Consultar mapeos en mapeo-api
    try:
        headers = {}
        mapeo_token = os.getenv("MAPEO_API_TOKEN")
        if mapeo_token:
            headers["Authorization"] = f"Bearer {mapeo_token}"
            
        m_api_res = requests.get(
            f"{mapeo_url}/mapeos?moodle_username={request.username}",
            headers=headers,
            timeout=5
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Mapeo API no disponible")
    
    if m_api_res.status_code != 200:
        raise HTTPException(status_code=503, detail="Error consultando cursos del usuario")

    mapeos = m_api_res.json()
    allowed_courses = []
    is_teacher = False
    moodle_user_id = None
    for m in mapeos:
        allowed_courses.append(m["moodle_course_id"])
        if m.get("is_teacher"):
            is_teacher = True
        if m.get("moodle_user_id"):
            moodle_user_id = m.get("moodle_user_id")

    # Inyectar mapeos mock si la base de datos está vacía (para pruebas UI)
    if not allowed_courses:
        if request.username in ("admin", "profesor1"):
            allowed_courses = [1, 3]
            is_teacher = True
            moodle_user_id = 1 if request.username == "admin" else 99
        elif request.username in ("alumno", "alumno1"):
            allowed_courses = [1, 3]
            is_teacher = False
            moodle_user_id = 2 if request.username == "alumno" else 100

    auditoria = AuditoriaAcceso(
        moodle_username=request.username,
        recurso="/token",
        resultado="SUCCESS",
        metadatos={"allowed_courses": allowed_courses, "is_teacher": is_teacher}
    )
    session.add(auditoria)

    payload = {
        "sub": request.username,
        "moodle_user_id": moodle_user_id,
        "is_teacher": is_teacher,
        "allowed_courses": allowed_courses,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    # Crear un Refresh Token real criptográficamente seguro
    raw_refresh_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
    
    # Guardarlo en base de datos
    db_rt = RefreshToken(
        moodle_user_id=moodle_user_id,
        token_hash=hashed_token,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
        revoked=0
    )
    session.add(db_rt)
    session.commit()
    
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60, # 7 days
    )
    
    return {"access_token": token, "token_type": "bearer"}

@app.post("/v1/refresh")
@app.post("/refresh", deprecated=True)
def refresh(request: Request, response: Response, session: Session = Depends(get_session)):

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token no encontrado")
        
    hashed_token = hashlib.sha256(refresh_token.encode()).hexdigest()
    db_token = session.query(RefreshToken).filter(RefreshToken.token_hash == hashed_token).first()
    
    if not db_token:
        raise HTTPException(status_code=401, detail="Refresh token inválido")
        
    if db_token.revoked == 1:
        # DETECCIÓN DE ROBO DE TOKEN:
        # Si alguien usa un token que ya fue revocado, purgar TODAS las sesiones de este usuario.
        session.query(RefreshToken).filter(RefreshToken.moodle_user_id == db_token.moodle_user_id).delete()
        session.commit()
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Token reuse detected. All sessions revoked.")
        
    if db_token.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expirado")
        
    # Rotación: revocar el token usado
    db_token.revoked = 1
    
    # Necesitamos reconstruir el payload JWT recuperando datos del usuario (usaremos el último log de acceso o consultaremos mapeo_api)
    # Por eficiencia, como el moodle_user_id es conocido, podemos consultar mapeo_api
    mapeo_url = os.getenv("MAPEO_API_URL")
    mapeo_token = os.getenv("MAPEO_API_TOKEN")
    try:
        headers = {}
        if mapeo_token:
            headers["Authorization"] = f"Bearer {mapeo_token}"
        m_api_res = requests.get(f"{mapeo_url}/mapeos?moodle_user_id={db_token.moodle_user_id}", headers=headers, timeout=5)
        if m_api_res.status_code != 200:
            raise Exception()
        mapeos = m_api_res.json()
    except:
        raise HTTPException(status_code=503, detail="Error de backend")
        
    if not mapeos:
        # Mock values para pruebas locales
        if db_token.moodle_user_id == 1:
            mapeos = [{"moodle_course_id": 1, "is_teacher": True, "moodle_username": "admin"}]
        else:
            mapeos = [{"moodle_course_id": 1, "is_teacher": False, "moodle_username": "alumno"}]
            
    allowed_courses = [m["moodle_course_id"] for m in mapeos]
    is_teacher = any(m.get("is_teacher") for m in mapeos)
    moodle_username = mapeos[0].get("moodle_username") if mapeos else "unknown"

    payload = {
        "sub": moodle_username,
        "moodle_user_id": db_token.moodle_user_id,
        "is_teacher": is_teacher,
        "allowed_courses": allowed_courses,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }
    access_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    # Generar NUEVO refresh token
    new_raw_token = secrets.token_urlsafe(32)
    new_hashed_token = hashlib.sha256(new_raw_token.encode()).hexdigest()
    
    new_db_token = RefreshToken(
        moodle_user_id=db_token.moodle_user_id,
        token_hash=new_hashed_token,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
        revoked=0
    )
    session.add(new_db_token)
    session.commit()
    
    response.set_cookie(
        key="refresh_token",
        value=new_raw_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/v1/logout")
@app.post("/logout", deprecated=True)
def logout(request: Request, response: Response, session: Session = Depends(get_session)):

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        hashed_token = hashlib.sha256(refresh_token.encode()).hexdigest()
        # Borrar el token de la DB explícitamente para revocarlo
        session.query(RefreshToken).filter(RefreshToken.token_hash == hashed_token).delete()
        session.commit()
        
    response.delete_cookie("refresh_token")
    return {"status": "ok"}

from metrics_api.agent import generar_resumen, seguimiento_resumen, get_timeline_detallado
from metrics_api.schemas import TimelineDetalladoResponse

@app.get("/v1/capacidades")
def get_capacidades():
    return {"ENABLE_EVALUATION_AGENT": os.getenv("ENABLE_EVALUATION_AGENT", "false").lower() == "true"}

@app.post("/v1/cursos/{curso_id}/estudiantes/{alumno_id}/resumen", response_model=AgentSummaryResponse)
async def api_generar_resumen(curso_id: int, alumno_id: int, user: AuthenticatedUser = Depends(verify_token)):
    verificar_permisos(curso_id, user)
    return await generar_resumen(curso_id, alumno_id)

@app.post("/v1/cursos/{curso_id}/estudiantes/{alumno_id}/resumen/seguimiento", response_model=AgentFollowUpResponse)
async def api_seguimiento_resumen(curso_id: int, alumno_id: int, req: AgentFollowUpRequest, user: AuthenticatedUser = Depends(verify_token)):
    verificar_permisos(curso_id, user)
    return await seguimiento_resumen(curso_id, alumno_id, req)

@app.get("/v1/cursos/{curso_id}/estudiantes/{alumno_id}/timeline_detallado", response_model=TimelineDetalladoResponse)
async def api_timeline_detallado(
    curso_id: int, 
    alumno_id: int, 
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(verify_token),
    session: Session = Depends(get_session)
):
    if not user.is_teacher and user.moodle_user_id != alumno_id:
        raise HTTPException(status_code=403, detail="No puedes ver el timeline de otro alumno")
    return await get_timeline_detallado(session, curso_id, alumno_id, limit, offset)
