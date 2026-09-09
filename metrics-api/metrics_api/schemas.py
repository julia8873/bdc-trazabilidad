from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

# Genéricos de paginación
class PaginatedResponse(BaseModel):
    """Respuesta paginada."""
    items: List[Any]
    total: int
    limit: int
    offset: int

class InteractionRead(BaseModel):
    """Lectura de interaccion."""
    id: UUID
    timestamp: datetime
    moodle_user_id: int
    moodle_course_id: int
    tipo_interaccion: str
    referencia_evento: Optional[str] = None
    metadatos: Optional[Dict[str, Any]] = None

    class Config:
        """Configuracion pydantic."""
        from_attributes = True

class PaginatedInteractions(PaginatedResponse):
    """Interacciones paginadas."""
    items: List[InteractionRead]

# Agregados
class CourseMetricsResponse(BaseModel):
    """Modelo para metricas de curso."""
    course_id: int
    total_interactions: int
    interactions_by_type: Dict[str, int]
    percentiles: Dict[str, Any] = {}

class StudentMetricsResponse(BaseModel):
    """Modelo para metricas de estudiante."""
    student_id: int
    course_id: int
    total_interactions: int
    interactions_by_type: Dict[str, int]
    repo_url: Optional[str] = None

class StudentCourseItem(BaseModel):
    """Item de curso para estudiante."""
    moodle_user_id: int
    moodle_username: str
    repo_url: Optional[str]
    total_interactions: int
    ultima_actividad: Optional[datetime] = None
    estado_sincronizacion: str = "OK"

class CourseStudentsResponse(BaseModel):
    """Modelo para lista de estudiantes."""
    course_id: int
    students: List[StudentCourseItem]

from typing import Literal

class CriterioEvaluacion(BaseModel):
    nombre: str
    observacion: str

class AgentSummaryResponse(BaseModel):
    estado: Literal["evaluado", "sin_actividad"]
    criterios: List[CriterioEvaluacion] = []
    fortalezas: List[str] = []
    patrones_uso: List[str] = []
    senales_alerta: List[str] = []
    version_rubrica: str = ""
    resumen_hash: str = ""

class AgentFollowUpMessage(BaseModel):
    rol: Literal["user", "assistant"]
    contenido: str

class AgentFollowUpRequest(BaseModel):
    mensaje: str
    historial: List[AgentFollowUpMessage] = []
    resumen_hash: str

class AgentFollowUpResponse(BaseModel):
    respuesta: str
    historial_actualizado: List[AgentFollowUpMessage] = []

# --- Fase 11: Extracción de interacciones ---

class InteraccionMetadatos(BaseModel):
    timestamp: str
    id: str  # id generado para poder consultarlo
    tipo_interaccion: str
    concepto: List[str]

class PaginatedInteraccionesMetadatos(PaginatedResponse):
    items: List[InteraccionMetadatos]

class InteraccionContenidoResponse(BaseModel):
    timestamp: str
    id: str
    mensaje_alumno: str
    respuesta_bot: str

class ConceptosFrecuenciasResponse(BaseModel):
    conceptos: Dict[str, int]

class RubricaCreate(BaseModel):
    instrucciones_agente: Optional[str] = None
    criterios: List[CriterioEvaluacion]

class RubricaRead(BaseModel):
    curso_id: int
    version: int
    instrucciones_agente: Optional[str] = None
    criterios: List[CriterioEvaluacion]
    created_at: datetime
    
    class Config:
        from_attributes = True
