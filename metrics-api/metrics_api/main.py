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
    AgentFollowUpResponse,
    RubricaRead,
    RubricaCreate
)
from metrics_api.repository import (
    get_course_aggregates,
    get_student_aggregates,
    get_interacciones_by_curso,
    get_interacciones_by_alumno,
    get_schema_version
)
from metrics_api.models import AuditoriaAcceso, RefreshToken, Rubrica

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
    import traceback
    traceback.print_exc()
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
async def get_student_metrics(response: Response, request: Request, 
    curso_id: int, estudiante_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):

    if not user.is_teacher and user.moodle_user_id != estudiante_id:
        raise HTTPException(status_code=403, detail="No puedes ver las métricas de otro alumno")
    # Verificamos si el alumno tiene actividad en general para retornar 404 o 200 con total=0
    # Como la regla dice "200 con total_interactions: 0 no 404", lo retornamos directamente.
    total, by_type = get_student_aggregates(session, estudiante_id, curso_id)
    
    from metrics_api.agent import get_mapeo
    mapeo = await get_mapeo(curso_id, estudiante_id)
    repo_url = mapeo.get("repo_url")
    
    return StudentMetricsResponse(
        student_id=estudiante_id,
        course_id=curso_id,
        total_interactions=total,
        interactions_by_type=by_type,
        repo_url=repo_url
    )

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes/{estudiante_id}/discrepancias")
async def get_student_discrepancias(
    curso_id: int, estudiante_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):
    if not user.is_teacher and user.moodle_user_id != estudiante_id:
        raise HTTPException(status_code=403, detail="No puedes ver las discrepancias de otro alumno")
        
    from metrics_api.models import DiscrepanciaAuditoria
    discrepancias = session.query(DiscrepanciaAuditoria).filter(
        DiscrepanciaAuditoria.moodle_user_id == estudiante_id,
        DiscrepanciaAuditoria.moodle_course_id == curso_id
    ).order_by(DiscrepanciaAuditoria.timestamp.desc()).all()
    
    return {
        "discrepancias": [
            {
                "id": d.id,
                "commit_sha": d.commit_sha,
                "tipo_discrepancia": d.tipo_discrepancia,
                "detalles": d.detalles,
                "timestamp": d.timestamp,
                "resuelta": d.resuelta,
                "resuelta_at": d.resuelta_at,
                "resuelta_por": d.resuelta_por,
                "commit_log_ref": d.commit_log_ref
            }
            for d in discrepancias
        ]
    }

@app.get("/v1/metrics/cursos/{curso_id}/discrepancias")
async def get_course_discrepancias(
    curso_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verificar_permisos)
):
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden ver las discrepancias del curso")
        
    from metrics_api.models import DiscrepanciaAuditoria
    discrepancias = session.query(DiscrepanciaAuditoria).filter(
        DiscrepanciaAuditoria.moodle_course_id == curso_id
    ).order_by(DiscrepanciaAuditoria.timestamp.desc()).limit(100).all()
    
    return {
        "discrepancias": [
            {
                "id": d.id,
                "moodle_user_id": d.moodle_user_id,
                "commit_sha": d.commit_sha,
                "tipo_discrepancia": d.tipo_discrepancia,
                "detalles": d.detalles,
                "timestamp": d.timestamp,
                "resuelta": d.resuelta,
                "resuelta_at": d.resuelta_at,
                "resuelta_por": d.resuelta_por,
                "commit_log_ref": d.commit_log_ref
            }
            for d in discrepancias
        ]
    }

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
            headers={"Host": os.getenv("MOODLE_HOST_HEADER", "localhost:8000")}, # Host esperado por defecto en el dev local
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
        raise HTTPException(status_code=403, detail="El usuario no tiene cursos asignados")
            
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

from metrics_api.agent import generar_resumen, seguimiento_resumen

@app.get("/v1/capacidades")
def get_capacidades():
    return {"ENABLE_EVALUATION_AGENT": os.getenv("ENABLE_EVALUATION_AGENT", "false").lower() == "true"}

@app.get("/v1/metrics/cursos/{curso_id}/rubrica", response_model=RubricaRead)
def get_rubrica(curso_id: int, user: AuthenticatedUser = Depends(verify_token), session: Session = Depends(get_session)):
    verificar_permisos(curso_id, user)
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden gestionar la rúbrica")
    
    from sqlalchemy import desc
    rubrica = session.query(Rubrica).filter(Rubrica.curso_id == curso_id).order_by(desc(Rubrica.version)).first()
    if not rubrica:
        raise HTTPException(status_code=404, detail="Rubrica personalizada no encontrada")
    return rubrica

@app.put("/v1/metrics/cursos/{curso_id}/rubrica", response_model=RubricaRead)
def put_rubrica(curso_id: int, req: RubricaCreate, user: AuthenticatedUser = Depends(verify_token), session: Session = Depends(get_session)):
    verificar_permisos(curso_id, user)
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden gestionar la rúbrica")
        
    from sqlalchemy import desc
    last_rubrica = session.query(Rubrica).filter(Rubrica.curso_id == curso_id).order_by(desc(Rubrica.version)).first()
    next_version = 1 if not last_rubrica else last_rubrica.version + 1
    
    new_rubrica = Rubrica(
        curso_id=curso_id,
        version=next_version,
        instrucciones_agente=req.instrucciones_agente,
        criterios=req.criterios
    )
    session.add(new_rubrica)
    session.commit()
    session.refresh(new_rubrica)
    return new_rubrica


@app.post("/v1/metrics/cursos/{curso_id}/estudiantes/{alumno_id}/resumen", response_model=AgentSummaryResponse)
async def api_generar_resumen(curso_id: int, alumno_id: int, user: AuthenticatedUser = Depends(verify_token), session: Session = Depends(get_session)):
    verificar_permisos(curso_id, user)
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden ver el resumen")
    return await generar_resumen(session, curso_id, alumno_id)

@app.post("/v1/metrics/cursos/{curso_id}/estudiantes/{alumno_id}/resumen/seguimiento", response_model=AgentFollowUpResponse)
async def api_seguimiento_resumen(curso_id: int, alumno_id: int, req: AgentFollowUpRequest, user: AuthenticatedUser = Depends(verify_token)):
    verificar_permisos(curso_id, user)
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden hacer seguimiento")
    return await seguimiento_resumen(curso_id, alumno_id, req)


# --- Endpoints de Sincronización Manual ---

async def _trigger_reconciliation_for_student(
    mapeo: dict,
    session: Session,
    current_user_id: int
):
    """
    Re-runs the reconciliation audit for a single student mapeo entry.
    Reuses the same logic as the metrics-worker but executed on-demand.
    Returns a dict with {'synced': int, 'discrepancias': int}.
    """
    import re as _re
    import httpx as _httpx
    from metrics_api.models import DiscrepanciaAuditoria, AuditoriaEstado
    from metrics_api.models import EventoSync
    from datetime import datetime

    repo_url = mapeo.get("repo_url")
    if not repo_url:
        return {"synced": 0, "discrepancias": 0}

    match = _re.search(r"github\.com/([^/]+)/([^/.]+)", repo_url)
    if not match:
        return {"synced": 0, "discrepancias": 0}

    owner, repo = match.groups()
    m_user_id = mapeo.get("moodle_user_id")
    m_course_id = mapeo.get("moodle_course_id")
    github_token = os.getenv("GITHUB_TOKEN_AGENT", os.getenv("GITHUB_TOKEN", ""))

    # Fetch commits from GitHub
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    commits = []
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=100"
    try:
        async with _httpx.AsyncClient() as client:
            while url:
                resp = await client.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    break
                commits.extend(resp.json())
                link_header = resp.headers.get("Link", "")
                next_url = None
                for part in link_header.split(","):
                    if 'rel="next"' in part:
                        next_url = part[part.index("<") + 1: part.index(">")]
                url = next_url
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fallo de comunicación con GitHub: {str(e)}")

    from metrics_api.models import Interaccion

    # 1. Get unresolved discrepancies instead of deleting them
    discrepancias_pendientes = session.query(DiscrepanciaAuditoria).filter(
        DiscrepanciaAuditoria.moodle_user_id == m_user_id,
        DiscrepanciaAuditoria.moodle_course_id == m_course_id,
        DiscrepanciaAuditoria.resuelta == 0
    ).all()
    discrepancias_dict = {d.commit_sha: d for d in discrepancias_pendientes}

    new_synced = 0
    mapeo_url = os.getenv("MAPEO_API_URL")
    mapeo_token = os.getenv("MAPEO_API_TOKEN")
    
    async with _httpx.AsyncClient() as client:
        for commit in commits:
            sha = commit.get("sha")
            if not sha:
                continue
    
            commit_msg = commit.get("commit", {}).get("message", "")
            # Only audit commits that follow the project's naming conventions
            KNOWN_PREFIXES = ("INGEST:", "REVERT:", "SYNC:", "INTERACCION:", "LOG:")
            if not any(commit_msg.startswith(p) for p in KNOWN_PREFIXES):
                continue
    
            existe_sync = session.query(EventoSync).filter(EventoSync.commit_sha == sha).first()
            
            if not existe_sync:
                # Sync the missing event
                db_event = EventoSync(
                    moodle_user_id=m_user_id,
                    moodle_course_id=m_course_id,
                    commit_sha=sha,
                    tipo_evento="INTERACTION" if commit_msg.startswith("INTERACCION:") else "INGEST",
                    estado="SUCCESS",
                    resultado={"verified_via_feed": False, "triggered_by": "manual_sync"}
                )
                session.add(db_event)
                
                try:
                    commit_date_str = commit.get("commit", {}).get("author", {}).get("date", "")
                    ts = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    ts = datetime.utcnow()
                    
                tipo = "chat" if commit_msg.startswith("INTERACCION:") else "file_upload"
                existe_int = session.query(Interaccion).filter(Interaccion.referencia_evento == sha).first()
                if not existe_int:
                    db_int = Interaccion(
                        moodle_user_id=m_user_id,
                        moodle_course_id=m_course_id,
                        tipo_interaccion=tipo,
                        referencia_evento=sha,
                        timestamp=ts
                    )
                    session.add(db_int)
                    
                # Paso 1: Ingerirá el commit huérfano de manera atómica
                try:
                    session.commit()
                    new_synced += 1
                except Exception as e:
                    print(f"ERROR COMMIT EVENTO/INTERACCION: {e}")
                    session.rollback()
                    continue
                    
            # Si hay una discrepancia para este commit, intentar resolverla
            if sha in discrepancias_dict:
                discr = discrepancias_dict[sha]
                
                # Paso 2: Llamar a mapeo-api para registrar en GitHub
                payload = {
                    "moodle_user_id": m_user_id,
                    "moodle_course_id": m_course_id,
                    "commit_sha": sha,
                    "tipo_discrepancia": discr.tipo_discrepancia,
                    "detalles": discr.detalles,
                    "resuelta_por": current_user_id,
                    "resuelta_at": datetime.utcnow().isoformat()
                }
                
                headers_mapeo = {}
                if mapeo_token:
                    headers_mapeo["Authorization"] = f"Bearer {mapeo_token}"
                    
                try:
                    res = await client.post(f"{mapeo_url}/v1/audit/discrepancias", json=payload, headers=headers_mapeo, timeout=10)
                    if res.status_code == 201:
                        # Paso 3: Llamada exitosa -> actualizar BD
                        discr.resuelta = 1
                        discr.resuelta_at = datetime.utcnow()
                        discr.resuelta_por = current_user_id
                        discr.commit_log_ref = res.json().get("commit_log_ref")
                        session.commit()
                except Exception as e:
                    # Paso 4: Llamada falla -> No marcar como resuelta
                    print(f"ERROR LLAMANDO MAPEO-API: {e}")
    return {"commits_checked": len(commits), "synced": new_synced, "discrepancias": 0}


@app.post("/v1/metrics/cursos/{curso_id}/estudiantes/{alumno_id}/sync")
async def api_sync_student(
    curso_id: int,
    alumno_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verify_token)
):
    """Triggers a manual reconciliation audit for a single student."""
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden sincronizar alumnos")
    if curso_id not in user.allowed_courses:
        raise HTTPException(status_code=403, detail="No tienes permiso para este curso")

    mapeo_url = os.getenv("MAPEO_API_URL")
    mapeo_token = os.getenv("MAPEO_API_TOKEN")
    headers = {}
    if mapeo_token:
        headers["Authorization"] = f"Bearer {mapeo_token}"

    try:
        m_res = requests.get(
            f"{mapeo_url}/mapeos?moodle_course_id={curso_id}",
            headers=headers,
            timeout=5
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Mapeo API no disponible")

    mapeos = m_res.json() if m_res.ok else []
    # Filter by student in Python — same pattern as get_course_students
    mapeo = next(
        (m for m in mapeos if m.get("moodle_user_id") == alumno_id and not m.get("is_teacher")),
        None
    )
    if not mapeo:
        raise HTTPException(status_code=404, detail="Alumno no encontrado en el mapeo del curso")

    result = await _trigger_reconciliation_for_student(mapeo, session, user.moodle_user_id)
    return {"status": "ok", "alumno_id": alumno_id, **result}


@app.post("/v1/metrics/cursos/{curso_id}/sync")
async def api_sync_course(
    curso_id: int,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(verify_token)
):
    """Triggers a manual reconciliation audit for all students with discrepancies in a course."""
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Solo profesores pueden sincronizar el curso")
    if curso_id not in user.allowed_courses:
        raise HTTPException(status_code=403, detail="No tienes permiso para este curso")

    from metrics_api.models import DiscrepanciaAuditoria

    mapeo_url = os.getenv("MAPEO_API_URL")
    mapeo_token = os.getenv("MAPEO_API_TOKEN")
    headers_mapeo = {}
    if mapeo_token:
        headers_mapeo["Authorization"] = f"Bearer {mapeo_token}"

    try:
        m_res = requests.get(
            f"{mapeo_url}/mapeos?moodle_course_id={curso_id}",
            headers=headers_mapeo,
            timeout=5
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Mapeo API no disponible")

    mapeos = m_res.json() if m_res.ok else []

    # Only process students that currently have discrepancies
    unsynced_ids = {
        row.moodle_user_id
        for row in session.query(DiscrepanciaAuditoria.moodle_user_id).filter(
            DiscrepanciaAuditoria.moodle_course_id == curso_id
        ).distinct()
    }

    total_synced = 0
    total_discrepancias = 0
    students_processed = 0

    errores = []
    for mapeo in mapeos:
        if mapeo.get("is_teacher"):
            continue
        uid = mapeo.get("moodle_user_id")
        if uid not in unsynced_ids:
            continue
        try:
            result = await _trigger_reconciliation_for_student(mapeo, session, user.moodle_user_id)
            total_synced += result["synced"]
            total_discrepancias += result["discrepancias"]
            students_processed += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_detail = getattr(e, "detail", str(e))
            errores.append({"moodle_user_id": uid, "error": error_detail})

    return {
        "status": "ok" if not errores else "partial",
        "students_processed": students_processed,
        "commits_checked": total_synced,
        "new_discrepancias": total_discrepancias,
        "errores": errores
    }


# --- FASE 11: Endpoints de Interacciones ---

import httpx
import json
import re
from fastapi import HTTPException
from metrics_api.agent import get_mapeo
from metrics_api.schemas import PaginatedInteraccionesMetadatos, InteraccionMetadatos, InteraccionContenidoResponse, ConceptosFrecuenciasResponse
from metrics_api.auth import AuthenticatedUser

async def get_all_jsonls_from_dir(repo_url: str, dir_path: str) -> list:
    github_token = os.getenv("GITHUB_TOKEN_AGENT")
    if not github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN_AGENT no configurado")
    
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        return []
    owner, repo = parts[-2], parts[-1].replace(".git", "")
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    import time
    cache_buster = int(time.time() * 1000)
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{dir_path}?ref=main&_cb={cache_buster}"
    print(f"DEBUG: Fetching directory from {url}")
    all_lines = []
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            print(f"DEBUG: Directory fetch status: {resp.status_code}")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            files = resp.json()
            if not isinstance(files, list):
                files = [files]
                
            import time
            cache_buster = int(time.time())
                
            print(f"DEBUG: Found {len(files)} files in directory")
            for file_info in files:
                if file_info["name"].endswith(".jsonl") and file_info["type"] == "file":
                    # Use API url to avoid 5-minute raw.githubusercontent cache
                    file_api_url = file_info["url"]
                    separator = "&" if "?" in file_api_url else "?"
                    file_api_url = f"{file_api_url}{separator}_cb={cache_buster}"
                    
                    print(f"DEBUG: Fetching file {file_info['name']} from {file_api_url}")
                    raw_resp = await client.get(file_api_url, headers=headers)
                    print(f"DEBUG: Status {raw_resp.status_code}")
                    if raw_resp.status_code == 200:
                        import base64
                        content_b64 = raw_resp.json().get("content", "")
                        print(f"DEBUG: Got b64 content len {len(content_b64)}")
                        if content_b64:
                            content = base64.b64decode(content_b64).decode('utf-8')
                            lines_found = 0
                            for line in content.splitlines():
                                if line.strip():
                                    try:
                                        all_lines.append(json.loads(line))
                                        lines_found += 1
                                    except:
                                        pass
                            print(f"DEBUG: Parsed {lines_found} JSON lines")
            return all_lines
        except Exception as e:
            print(f"DEBUG: Exception {e}")
            raise HTTPException(status_code=500, detail=f"Error leyendo de GitHub: {str(e)}")

def redactar_pii(texto: str) -> str:
    if not isinstance(texto, str):
        return texto
    # Redactar emails
    texto = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[DATO REDACTADO]', texto)
    # Redactar secuencias de 8 o más dígitos, opcionalmente terminadas en letra (como DNI)
    texto = re.sub(r'\b\d{8,}[a-zA-Z]?\b', '[DATO REDACTADO]', texto)
    return texto

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes/{alumno_id}/interacciones", response_model=PaginatedInteraccionesMetadatos)
async def get_interacciones_metadatos(
    curso_id: int, 
    alumno_id: int,
    tipo: Optional[str] = None,
    concepto: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(verificar_permisos)
):
    if not user.is_teacher and user.moodle_user_id != alumno_id:
        raise HTTPException(status_code=403, detail="No puedes ver esto")
        
    mapeo = await get_mapeo(curso_id, alumno_id)
    repo_url = mapeo.get("repo_url")
    if not repo_url:
        return PaginatedInteraccionesMetadatos(items=[], total=0, limit=limit, offset=offset)
        
    data = await get_all_jsonls_from_dir(repo_url, "logs/interacciones")
    
    # TODO (Fase 13): Eliminar este bloque de compatibilidad temporal una vez confirmado que no quedan 
    # ficheros JSONL con formato antiguo (pre-11.1) en ningún repositorio de alumno activo.
    # COMPATIBILIDAD TEMPORAL: datos históricos (formato pre-11.1) tienen dos líneas por interacción.
    seen_timestamps: set[str] = set()
    dedup_data = []
    for d in data:
        ts = d.get("timestamp", "")
        has_tipo = "tipo_interaccion" in d
        if ts in seen_timestamps:
            continue  # ya procesamos este timestamp (preferimos el registro con tipo)
        if not has_tipo and any(
            other.get("timestamp") == ts and "tipo_interaccion" in other
            for other in data
        ):
            continue  # hay un registro con tipo_interaccion para este ts — saltamos el crudo
        seen_timestamps.add(ts)
        dedup_data.append(d)
        
    data = dedup_data
    
    # Filtrar
    filtered = []
    for d in data:
        t = d.get("tipo_interaccion", "")
        c = d.get("concepto", [])
        if tipo and tipo != t:
            continue
        if concepto and concepto not in c:
            continue
            
        # Filtrado search SÓLO en metadatos para evitar PII
        if search:
            search_lower = search.lower()
            t_lower = t.lower() if t else ""
            c_lower = [str(concept).lower() for concept in c]
            if search_lower not in t_lower and not any(search_lower in concept for concept in c_lower):
                continue
        
        # ID generado a partir del timestamp para usarlo en contenido
        ts = d.get("timestamp", "")
        import hashlib
        id_str = hashlib.sha256(ts.encode()).hexdigest()[:16]
        
        filtered.append(InteraccionMetadatos(
            timestamp=ts,
            id=id_str,
            tipo_interaccion=t,
            concepto=c
        ))
        
    # Ordenar
    if sort_by == "timestamp":
        reverse = (sort_dir == "desc") if sort_dir else True
        filtered.sort(key=lambda x: x.timestamp, reverse=reverse)
    elif sort_by == "tipo_interaccion":
        reverse = (sort_dir == "desc") if sort_dir else False
        filtered.sort(key=lambda x: x.tipo_interaccion, reverse=reverse)
    else:
        # Sort data descending by timestamp by default
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        
    paginated = filtered[offset:offset+limit]
    return PaginatedInteraccionesMetadatos(items=paginated, total=len(filtered), limit=limit, offset=offset)

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes/{alumno_id}/conceptos", response_model=ConceptosFrecuenciasResponse)
async def get_conceptos_frecuencias(
    curso_id: int, 
    alumno_id: int,
    user: AuthenticatedUser = Depends(verificar_permisos)
):
    if not user.is_teacher and user.moodle_user_id != alumno_id:
        raise HTTPException(status_code=403, detail="No puedes ver esto")
    
    if user.is_teacher and curso_id not in user.allowed_courses:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este curso")
        
    mapeo = await get_mapeo(curso_id, alumno_id)
    repo_url = mapeo.get("repo_url")
    if not repo_url:
        return ConceptosFrecuenciasResponse(conceptos={})
        
    data = await get_all_jsonls_from_dir(repo_url, "logs/interacciones")
    
    conceptos_dict = {}
    for d in data:
        # Solo contamos si no es fuera_de_ambito, o los contamos todos? 
        # La instrucción dice "Muestra, por concepto, cuántas veces se ha tratado". Los fuera_de_ambito no tienen conceptos relevantes o si tienen, no cuentan. Asumiremos contar todos los conceptos presentes.
        c_list = d.get("concepto", [])
        for c in c_list:
            if c:
                conceptos_dict[c] = conceptos_dict.get(c, 0) + 1
                
    return ConceptosFrecuenciasResponse(conceptos=conceptos_dict)

@app.get("/v1/metrics/cursos/{curso_id}/estudiantes/{alumno_id}/interacciones/{interaccion_id}/contenido", response_model=InteraccionContenidoResponse)
async def get_interaccion_contenido(
    curso_id: int, 
    alumno_id: int,
    interaccion_id: str,
    user: AuthenticatedUser = Depends(verificar_permisos),
    session: Session = Depends(get_session)
):
    if not user.is_teacher and user.moodle_user_id != alumno_id:
        raise HTTPException(status_code=403, detail="No puedes ver esto")
        
    mapeo = await get_mapeo(curso_id, alumno_id)
    repo_url = mapeo.get("repo_url")
    if not repo_url:
        raise HTTPException(status_code=404, detail="Repo no encontrado")
        
    data = await get_all_jsonls_from_dir(repo_url, "logs/interacciones")
    import hashlib
    
    for d in data:
        ts_str = d.get("timestamp", "")
        if not ts_str:
            continue
            
        id_str = hashlib.sha256(ts_str.encode()).hexdigest()[:16]
        if id_str == interaccion_id:
            msg = d.get("mensaje_alumno")
            bot = d.get("respuesta_bot")
            
            # TODO (Fase 13): Bloque de compatibilidad temporal (formato pre-11.1)
            if msg is None and bot is None:
                for other in data:
                    if other.get("timestamp") == ts_str and "mensaje_alumno" in other:
                        msg = other.get("mensaje_alumno", "")
                        bot = other.get("respuesta_bot", "")
                        break
            else:
                msg = msg or ""
                bot = bot or ""
                
            return InteraccionContenidoResponse(
                timestamp=ts_str,
                id=interaccion_id,
                mensaje_alumno=redactar_pii(msg),
                respuesta_bot=redactar_pii(bot)
            )
            
    raise HTTPException(status_code=404, detail="Contenido no encontrado en los logs de GitHub")

