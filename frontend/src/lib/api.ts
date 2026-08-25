export const API_URL = '/api';

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface UserToken {
  sub: string;
  moodle_user_id: number | null;
  is_teacher: boolean;
  allowed_courses: number[];
  exp: number;
}

export interface Interaction {
  id: string;
  timestamp: string;
  moodle_user_id: number;
  moodle_course_id: number;
  tipo_interaccion: string;
  referencia_evento: string | null;
  metadatos: any | null;
}

export interface PaginatedInteractions {
  items: Interaction[];
  total: number;
  limit: number;
  offset: number;
}

export interface CourseMetrics {
  course_id: number;
  total_interactions: number;
  interactions_by_type: Record<string, number>;
  percentiles: {
    p25: number;
    p50: number;
    p75: number;
    p90: number;
    unique_users: number;
  };
}

export interface StudentMetrics {
  student_id: number;
  course_id: number;
  total_interactions: number;
  interactions_by_type: Record<string, number>;
}
