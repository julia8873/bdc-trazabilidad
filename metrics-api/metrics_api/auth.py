import os
import jwt
from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from metrics_api.db import get_session
from metrics_api.models import AuditoriaAcceso

security = HTTPBearer()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme_in_production")
JWT_ALGORITHM = "HS256"

class AuthenticatedUser(BaseModel):
    is_authenticated: bool
    moodle_username: str
    moodle_user_id: Optional[int] = None
    is_teacher: bool = False
    allowed_courses: List[int] = []

def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> AuthenticatedUser:
    token = credentials.credentials
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        sub = unverified.get("sub", "unknown")
    except Exception:
        sub = "unknown"

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return AuthenticatedUser(
            is_authenticated=True,
            moodle_username=payload.get("sub"),
            moodle_user_id=payload.get("moodle_user_id"),
            is_teacher=payload.get("is_teacher", False),
            allowed_courses=payload.get("allowed_courses", [])
        )
    except jwt.ExpiredSignatureError:
        auditoria = AuditoriaAcceso(
            moodle_username=sub,
            recurso=request.url.path,
            resultado="EXPIRED_JWT",
            metadatos={"ip": request.client.host if request.client else "unknown"}
        )
        session.add(auditoria)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        auditoria = AuditoriaAcceso(
            moodle_username=sub,
            recurso=request.url.path,
            resultado="INVALID_JWT",
            metadatos={"ip": request.client.host if request.client else "unknown"}
        )
        session.add(auditoria)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verificar_permisos(course_id: int, user: AuthenticatedUser = Depends(verify_token)):
    if course_id not in user.allowed_courses:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Acceso denegado a este curso"
        )
    return user
