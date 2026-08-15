"""
Modelos SQLAlchemy para el esquema `metrics` de bdc-trazabilidad.

Todas las tablas viven en el esquema `metrics` (propiedad de metrics_user),
aisladas del esquema `public` de mapeo-api por política de permisos de BD.

Asunciones documentadas (borrador pendiente de validación de dominio diferida):
- moodle_user_id / moodle_course_id son FKs lógicas hacia mapeo-api;
  la integridad referencial se garantiza en la capa de aplicación
  (GET /mapeos antes de escribir), no mediante FK de BD entre esquemas.
- eventos_sync no lleva moodle_user_id/moodle_course_id todavía;
  pendiente confirmar si el dashboard necesitará filtrar por alumno/curso.
- El catálogo de conceptos (tabla `conceptos`) existe pero está vacío;
  la población real contra los AGENTS.md de cada curso es trabajo de Fase 3.
- Los campos en `metadatos` (JSONB) son zona de aterrizaje provisional;
  ver política de promoción en docs/esquema-metrics.md.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import MetaData

metadata_obj = MetaData(schema="metrics")
Base = declarative_base(metadata=metadata_obj)


class Concepto(Base):
    """
    Catálogo normalizado de conceptos pedagógicos por curso.

    Un concepto es único por (curso_id, nombre): el índice único compuesto
    evita duplicados dentro del mismo curso.

    Pendiente (Fase 3): poblar esta tabla a partir de los AGENTS.md de cada
    curso. Hasta que se haga, conceptos_detectados no puede referenciar
    conceptos reales y la detección automatizada no tiene catálogo con el
    que comparar.
    """
    __tablename__ = "conceptos"
    __table_args__ = (
        UniqueConstraint("curso_id", "nombre", name="uq_concepto_curso_nombre"),
        {"schema": "metrics"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    # FK lógica hacia moodle_course_id (igual que en Interaccion); no FK de BD
    # porque el curso vive en mapeo-api/esquema public, no en metrics.
    curso_id = Column(Integer, nullable=False)

    detecciones = relationship("ConceptoDetectado", back_populates="concepto")


class Interaccion(Base):
    """
    Registro de cada interacción de un alumno con el sistema LLM.

    metadatos (JSONB) es zona de aterrizaje para campos cuya necesidad de
    estructuración aún no está validada. Ver política de promoción en
    docs/esquema-metrics.md antes de añadir consultas frecuentes sobre claves
    concretas de este campo.
    """
    __tablename__ = "interacciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    moodle_user_id = Column(Integer, index=True, nullable=False)
    moodle_course_id = Column(Integer, index=True, nullable=False)
    tipo_interaccion = Column(String, nullable=False)
    referencia_evento = Column(String, nullable=True)
    metadatos = Column(JSONB, nullable=True)

    conceptos = relationship("ConceptoDetectado", back_populates="interaccion", cascade="all, delete-orphan")
    reversiones = relationship("Reversion", back_populates="interaccion", cascade="all, delete-orphan")


class ConceptoDetectado(Base):
    """
    Asociación entre una interacción y un concepto del catálogo.

    concepto_id es FK real hacia conceptos.id (no texto libre).
    Migración: esta tabla fue recreada desde cero en la migración
    `catalogo_conceptos` (v2). Si hubiera datos reales en la versión anterior
    (concepto como String), haría falta una migración de datos explícita en
    vez del DROP/CREATE usado aquí (válido solo en fase de desarrollo sin datos).
    """
    __tablename__ = "conceptos_detectados"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaccion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interacciones.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    concepto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conceptos.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    interaccion = relationship("Interaccion", back_populates="conceptos")
    concepto = relationship("Concepto", back_populates="detecciones")


class EventoSync(Base):
    """
    Registro de eventos de sincronización entre sistemas.

    Nota pendiente de validación: no lleva moodle_user_id/moodle_course_id.
    Si el dashboard necesita filtrar eventos por alumno o curso, habrá que
    añadirlos mediante una migración aditiva en Fase 3/4.
    """
    __tablename__ = "eventos_sync"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    moodle_user_id = Column(Integer, nullable=True)
    moodle_course_id = Column(Integer, nullable=True)
    commit_sha = Column(String, nullable=True)
    tipo_evento = Column(String, nullable=False)
    estado = Column(String, nullable=False)
    resultado = Column(JSONB, nullable=True)


class DiscrepanciaAuditoria(Base):
    """
    Registro de discrepancias detectadas por el auditor de GitHub.
    """
    __tablename__ = "discrepancias_auditoria"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    moodle_user_id = Column(Integer, nullable=True)
    moodle_course_id = Column(Integer, nullable=True)
    commit_sha = Column(String, nullable=False, index=True)
    tipo_discrepancia = Column(String, nullable=False)
    detalles = Column(JSONB, nullable=True)


class AuditoriaEstado(Base):
    """
    Guarda el cursor (último commit timestamp verificado) para auditoría incremental.
    """
    __tablename__ = "auditoria_estado"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    moodle_user_id = Column(Integer, nullable=False)
    moodle_course_id = Column(Integer, nullable=False)
    repo_owner = Column(String, nullable=False)
    repo_name = Column(String, nullable=False)
    last_audited_timestamp = Column(DateTime, nullable=False)


class Reversion(Base):
    """
    Registro de reversiones de interacciones.

    Asunción documentada: toda reversion referencia una interaccion existente.
    La FK real (ondelete=CASCADE) garantiza que no queden reversiones huérfanas.
    """
    __tablename__ = "reversiones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaccion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interacciones.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    interaccion = relationship("Interaccion", back_populates="reversiones")


class AuditoriaAcceso(Base):
    """
    Registro inmutable de intentos de acceso a recursos de la API.
    A nivel de BD, un TRIGGER impide UPDATE o DELETE (append-only estricto).
    """
    __tablename__ = "auditoria_accesos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    moodle_username = Column(String, index=True, nullable=False)
    recurso = Column(String, nullable=False)
    resultado = Column(String, nullable=False)
    metadatos = Column(JSONB, nullable=True)
