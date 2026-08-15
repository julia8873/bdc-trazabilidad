from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

# Genéricos de paginación
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int

class InteractionRead(BaseModel):
    id: UUID
    timestamp: datetime
    moodle_user_id: int
    moodle_course_id: int
    tipo_interaccion: str
    referencia_evento: Optional[str] = None
    metadatos: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class PaginatedInteractions(PaginatedResponse):
    items: List[InteractionRead]

# Agregados
class CourseMetricsResponse(BaseModel):
    course_id: int
    total_interactions: int
    interactions_by_type: Dict[str, int]
    percentiles: Dict[str, Any] = {}

class StudentMetricsResponse(BaseModel):
    student_id: int
    course_id: int
    total_interactions: int
    interactions_by_type: Dict[str, int]

class StudentCourseItem(BaseModel):
    moodle_user_id: int
    moodle_username: str
    repo_url: Optional[str]
    total_interactions: int
    ultima_actividad: Optional[datetime] = None
    estado_sincronizacion: str = "OK"

class CourseStudentsResponse(BaseModel):
    course_id: int
    students: List[StudentCourseItem]
