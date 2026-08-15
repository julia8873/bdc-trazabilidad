"""
Capa de acceso a datos (Repository Pattern) para el esquema `metrics`.

Convención para Fase 4: todos los endpoints HTTP de metrics-api deben
consumir estas funciones en vez de construir queries SQLAlchemy directamente
en los handlers. Esto mantiene la lógica de acceso a datos centralizada y
testeable sin levantar un servidor HTTP.

Funciones disponibles:
  - get_interacciones_by_curso(session, curso_id, limit, offset) -> (List[Interaccion], int)
  - get_interacciones_by_alumno(session, moodle_user_id, curso_id, limit, offset) -> (List[Interaccion], int)
  - get_course_aggregates(session, curso_id) -> (int, dict)
  - get_student_aggregates(session, moodle_user_id, curso_id) -> (int, dict)
  - get_conceptos_by_curso(session, curso_id) -> List[Concepto]
  - get_schema_version(session) -> str | None
"""

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from metrics_api.models import Interaccion, Concepto


def get_interacciones_by_curso(session: Session, curso_id: int, limit: int = 10, offset: int = 0) -> tuple[list, int]:
    """
    Devuelve las interacciones paginadas y el total para un curso.
    """
    query = session.query(Interaccion).filter(Interaccion.moodle_course_id == curso_id)
    total = query.count()
    items = query.order_by(Interaccion.timestamp.desc()).offset(offset).limit(limit).all()
    return items, total


def get_interacciones_by_alumno(session: Session, moodle_user_id: int, curso_id: int, limit: int = 10, offset: int = 0) -> tuple[list, int]:
    """
    Devuelve las interacciones paginadas y el total para un alumno en un curso.
    """
    query = session.query(Interaccion).filter(
        Interaccion.moodle_user_id == moodle_user_id,
        Interaccion.moodle_course_id == curso_id
    )
    total = query.count()
    items = query.order_by(Interaccion.timestamp.desc()).offset(offset).limit(limit).all()
    return items, total


def get_course_aggregates(session: Session, curso_id: int) -> tuple[int, dict, dict]:
    """
    Devuelve el total de interacciones, la agregación por tipo y percentiles para un curso.
    """
    total = session.query(Interaccion).filter(Interaccion.moodle_course_id == curso_id).count()
    
    aggs = session.query(Interaccion.tipo_interaccion, func.count(Interaccion.id)).filter(
        Interaccion.moodle_course_id == curso_id
    ).group_by(Interaccion.tipo_interaccion).all()
    
    by_type = {row[0]: row[1] for row in aggs}
    
    # Calcular percentiles
    sql = text("""
        WITH user_counts AS (
            SELECT moodle_user_id, count(id) AS interaction_count
            FROM metrics.interacciones
            WHERE moodle_course_id = :curso_id
            GROUP BY moodle_user_id
        )
        SELECT 
            percentile_cont(0.25) WITHIN GROUP (ORDER BY interaction_count),
            percentile_cont(0.50) WITHIN GROUP (ORDER BY interaction_count),
            percentile_cont(0.75) WITHIN GROUP (ORDER BY interaction_count),
            percentile_cont(0.90) WITHIN GROUP (ORDER BY interaction_count),
            count(*) as unique_users
        FROM user_counts;
    """)
    res = session.execute(sql, {"curso_id": curso_id}).fetchone()
    
    percentiles = {
        "p25": float(res[0]) if res and res[0] is not None else 0.0,
        "p50": float(res[1]) if res and res[1] is not None else 0.0,
        "p75": float(res[2]) if res and res[2] is not None else 0.0,
        "p90": float(res[3]) if res and res[3] is not None else 0.0,
        "unique_users": int(res[4]) if res and res[4] is not None else 0
    }
    
    return total, by_type, percentiles


def get_student_aggregates(session: Session, moodle_user_id: int, curso_id: int) -> tuple[int, dict]:
    """
    Devuelve el total de interacciones y la agregación por tipo para un alumno en un curso.
    """
    total = session.query(Interaccion).filter(
        Interaccion.moodle_user_id == moodle_user_id,
        Interaccion.moodle_course_id == curso_id
    ).count()
    
    aggs = session.query(Interaccion.tipo_interaccion, func.count(Interaccion.id)).filter(
        Interaccion.moodle_user_id == moodle_user_id,
        Interaccion.moodle_course_id == curso_id
    ).group_by(Interaccion.tipo_interaccion).all()
    
    by_type = {row[0]: row[1] for row in aggs}
    return total, by_type


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
