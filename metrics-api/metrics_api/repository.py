"""
Capa de acceso a datos (Repository Pattern) para el esquema `metrics`.

Convención para Fase 4: todos los endpoints HTTP de metrics-api deben
consumir estas funciones en vez de construir queries SQLAlchemy directamente
en los handlers. Esto mantiene la lógica de acceso a datos centralizada y
testeable sin levantar un servidor HTTP.

Funciones disponibles:
  - get_interacciones_by_curso(session, curso_id) -> List[Interaccion]
  - get_interacciones_by_alumno(session, moodle_user_id) -> List[Interaccion]
  - get_conceptos_by_curso(session, curso_id) -> List[Concepto]
  - get_schema_version(session) -> str | None
"""

from sqlalchemy.orm import Session
from sqlalchemy import text

from metrics_api.models import Interaccion, Concepto


def get_interacciones_by_curso(session: Session, curso_id: int) -> list:
    """
    Devuelve todas las interacciones registradas para un curso dado.

    Usado en Fase 4 por el endpoint GET /metrics/course/{curso_id}.
    """
    return (
        session.query(Interaccion)
        .filter(Interaccion.moodle_course_id == curso_id)
        .order_by(Interaccion.timestamp.desc())
        .all()
    )


def get_interacciones_by_alumno(session: Session, moodle_user_id: int) -> list:
    """
    Devuelve todas las interacciones registradas para un alumno dado.

    Usado en Fase 4 por el endpoint GET /metrics/student/{moodle_user_id}.
    """
    return (
        session.query(Interaccion)
        .filter(Interaccion.moodle_user_id == moodle_user_id)
        .order_by(Interaccion.timestamp.desc())
        .all()
    )


def get_conceptos_by_curso(session: Session, curso_id: int) -> list:
    """
    Devuelve los conceptos del catálogo registrados para un curso dado.

    Nota: el catálogo estará vacío hasta que se realice la población desde
    los AGENTS.md de cada curso (Fase 3).
    """
    return (
        session.query(Concepto)
        .filter(Concepto.curso_id == curso_id)
        .order_by(Concepto.nombre)
        .all()
    )


def get_schema_version(session: Session) -> str | None:
    """
    Devuelve la revisión actual de Alembic desde la tabla
    `metrics.alembic_version`.

    Decisión de implementación: se lee directamente de la BD en vez de
    mantener una constante en código, para que la versión refleje siempre
    el estado real de las migraciones aplicadas y no dependa de una
    sincronización manual en cada release.

    Devuelve None si la tabla no existe o está vacía (BD no inicializada).
    """
    try:
        result = session.execute(
            text("SELECT version_num FROM metrics.alembic_version LIMIT 1")
        ).fetchone()
        return result[0] if result else None
    except Exception:
        return None
