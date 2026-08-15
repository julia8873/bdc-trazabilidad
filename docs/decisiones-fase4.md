# Decisiones de Diseño y Arquitectura - Fase 4 (metrics-api)

Este documento registra las decisiones tomadas durante la implementación de la Fase 4 de `metrics-api`, garantizando que quede constancia del "por qué" para futuras fases (especialmente Fase 5 de Autorización y Fase 6 de Frontend).

## 1. Autenticación (Bearer Token)
Se implementó un patrón de validación simple por Bearer Token (`HTTPBearer`) leyendo la variable de entorno `METRICS_API_TOKEN`.

**Decisión**: Se **replicó** el código de validación de `mapeo-api` en lugar de extraerlo como dependencia cruzada real en `shared-pkg`.
**Justificación**: 
El mecanismo consta de apenas unas 10 líneas de código utilizando herramientas nativas de FastAPI. Extraerlo habría introducido un acoplamiento rígido de seguridad entre ambas APIs (obligándolas a compartir la misma versión del paquete de seguridad) para ahorrar un código trivial. Replicarlo permite que cada API evolucione su mecanismo (rotación, scopes) sin romperse mutuamente. 
*Nota*: Como resultado, **no hay dependencia de código real añadida** por esta decisión, y por ende no requiere entrada en `docs/integracion-bdc.md`.

## 2. Diseño de Endpoints de Agregación y Listado

**Decisión**: Se escogió la **Opción A**, separando puramente los endpoints de métricas agregadas y los de listado paginado:
- `GET /metrics/course/{id}`: Retorna contadores agregados (total de interacciones, interacciones por tipo).
- `GET /metrics/course/{id}/interactions`: Retorna la lista paginada de interacciones puras.

**Justificación**:
Mantenerlos separados optimiza el rendimiento y la flexibilidad para el dashboard (Fase 6).
- **Caché**: Permite cachear los contadores pesados de forma independiente al flujo (scroll) de la tabla de interacciones.
- **Filtros**: Facilita enormemente añadir filtros (`?type=...` o `?from_date=...`) en la Fase 6. Si estuvieran mezclados, habría ambigüedad semántica sobre si un filtro de fecha en la URL afecta a los contadores globales o solo a los items paginados devueltos. Separarlos elimina esta ambigüedad desde el diseño.

Esta decisión aplica idénticamente a `/metrics/course/{course_id}/student/{student_id}` y `/metrics/course/{course_id}/student/{student_id}/interactions`.

## 3. Jerarquía REST: Métricas de Estudiante Anidadas bajo Curso

**Decisión**: La ruta para obtener las métricas de un estudiante cambió de `GET /metrics/student/{id}?course_id=...` (diseño original) a una ruta anidada estricta: `GET /metrics/course/{course_id}/student/{student_id}`.

**Justificación**: 
En el contexto de la analítica de aprendizaje del proyecto, las métricas de un alumno *siempre* están fuertemente acopladas al contexto de una asignatura concreta (curso). Un `student_id` suelto carece de sentido para calcular "interacciones totales" a menos que queramos agregar globalmente toda su actividad en la universidad (lo cual no es el objetivo de esta API). Al forzar la anidación semántica (`/course/.../student/...`), el contrato REST hace que el `course_id` sea obligatorio por diseño estructural de la URL, no un *query parameter* que el consumidor pueda omitir accidentalmente. Esto aporta consistencia con el agrupamiento de los endpoints base de curso.
