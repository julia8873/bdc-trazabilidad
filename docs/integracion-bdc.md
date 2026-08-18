# Integración y Acoplamiento: bdc-trazabilidad & llm-wiki-assistant

Este documento define la estrategia de integración, acoplamiento y dependencias cruzadas entre el proyecto `bdc-trazabilidad` (dashboard de trazabilidad y métricas) y el sistema base `llm-wiki-assistant`.

## 1. Naturaleza de los Repositorios

`bdc-trazabilidad` se mantiene como un repositorio independiente de `llm-wiki-assistant` porque tiene un ciclo de vida, un dominio funcional y unos requisitos de escalabilidad distintos. Sin embargo, en el entorno de desarrollo automatizado, ambos repositorios son accesibles simultáneamente (y con permisos de escritura) para permitir una integración fluida y la gestión coordinada de infraestructuras sin perder la separación lógica.

## 2. Ejes de Acoplamiento

El proyecto define tres ejes de acoplamiento claros y controlados:

### A. Acoplamiento de Código (Bidireccional Permitido)
Se permite el acoplamiento de código bidireccional entre ambos repositorios, siempre que aporte valor frente a otras alternativas (como API HTTP o reimplementación de lógica) y **cumpla estrictamente las 8 Reglas de Dependencia Cruzada** definidas en este documento.

### B. Esquema de Base de Datos (Aislamiento Estricto)
**El acoplamiento a nivel de esquema de base de datos está prohibido.** 
La decisión arquitectónica es que `bdc-trazabilidad` utilizará un esquema de base de datos propio llamado `metrics`, pero alojado en la misma instancia física de PostgreSQL de producción que usa `mapeo-api` (parte de `llm-wiki-assistant`).
Para garantizar el aislamiento por RGPD/LOPD, el esquema `metrics` tendrá su propio usuario de BD con permisos acotados exclusivamente a dicho esquema.

### C. Infraestructura de Despliegue y CI/CD (Acoplamiento Deliberado)
La infraestructura de despliegue en producción se acopla deliberadamente a través de una **costura única**: el fichero `deploy/docker-compose.prod.yml` de este repositorio (`bdc-trazabilidad`).

- **Costura de Orquestación:** Este fichero utiliza la directiva `include:` de Docker Compose para integrar los servicios de `llm-wiki-assistant` (referenciados mediante ruta relativa `../../llm-wiki-assistant/moodle-matrix-dev/docker-compose.yml`).
- **Red Compartida (`bdc-net`):** Para permitir que los servicios de ambos proyectos se comuniquen, se ha inyectado la declaración de una red externa `bdc-net` en el `docker-compose.yml` de `llm-wiki-assistant`, y se ha añadido a los servicios `mapeo-api`, `postgres` y `redis`.
- **CI/CD Compartido:** Se utiliza un workflow reutilizable (`.github/workflows/deploy-reusable.yml`) alojado en `llm-wiki-assistant`, que es invocado desde los
### Detección de Ciclos de Dependencia (Python)
Para prevenir dependencias circulares a nivel de paquete (ej. `metrics-api` -> `shared-pkg` -> `metrics-api`), el CI de **bdc-trazabilidad** ejecuta un script de validación estática (`scripts/detect_cycles.py`).
Este script utiliza `tomllib` (nativo en Python 3.11+) para extraer las dependencias reales del bloque `[project.dependencies]` de todos los archivos `pyproject.toml` descubiertos en el workspace de ambos repositorios.
A continuación, construye un grafo dirigido y realiza una búsqueda en profundidad (DFS) estricta. Si se detecta un ciclo, el script retorna código de salida 1, abortando el pipeline de integración continua. `include:` de `bdc-trazabilidad/deploy/docker-compose.prod.yml`.
  2. Eliminar la red `bdc-net` y las referencias a ella del fichero `llm-wiki-assistant/moodle-matrix-dev/docker-compose.yml`.
  3. Desvincular la llamada al workflow reutilizable en `.github/workflows/ci.yml`.
- ⚠️ **Aviso Explícito:** Si revertir cualquier acoplamiento (de infraestructura o de código) requiere modificar más código o configuración de lo estrictamente necesario, es señal de que se implementó de forma incorrecta y debe ser refactorizado inmediatamente.

---

## 3. Las 8 Reglas de Dependencia Cruzada de Código

Toda dependencia de código entre repositorios deberá cumplir:

1. **Dirección documentada por caso de uso:** Registrada en la tabla de este documento.
2. **Prohibido el ciclo de dependencia:** Ni directo ni transitivo.
3. **Empaquetado versionado:** Nunca mediante imports frágiles, alteraciones de `sys.path` ni rutas relativas tipo `../../`.
4. **Tests del repo modificado:** Deben pasar antes y después de cualquier cambio en ambos repositorios.
5. **Test de compatibilidad cruzada:** Obligatorio en CI antes de fusionar cambios que afecten al otro repositorio.
6. **Cambios aditivos por defecto:** Alterar comportamiento existente solo si es estrictamente necesario y justificado por escrito.
7. **Commits separados por repositorio:** Claramente etiquetados (ej. `feat(llm-wiki-assistant): ...` vs `feat(bdc-trazabilidad): ...`).
8. **Rollback documentado:** Para cada dependencia cruzada nueva.

## 4. Mecanismo de Empaquetado

Cuando se requiera importar código de un repositorio a otro, se utilizará un mecanismo formal de empaquetado:
- El repositorio que exponga el código reutilizable deberá empaquetarlo (mediante un `pyproject.toml` instalable).
- Se versionará explícitamente con tags semánticos (SemVer).
- 3. **Versionado Explícito:** El repositorio consumidor (`bdc-trazabilidad`) debe fijar la versión exacta de las dependencias que consume (ej. una versión de API o un tag de imagen Docker). **Nunca apunta a `main` o `latest` en producción.**
   > **Nota aclaratoria sobre CI/CD:** Esta regla aplica estrictamente a los despliegues de producción y resolución de dependencias del runtime. En los pipelines de Integración Continua (CI), cuando se dispara un test de compatibilidad cruzada (`repository_dispatch`), el CI comprueba la versión entrante del proveedor contra la rama principal de desarrollo (`main`) del consumidor. Esto no viola la Regla 3, ya que el propósito del CI es probar si el código nuevo rompe la rama de desarrollo actual *antes* de aprobar el cambio, no definir la versión estática de despliegue.
- 4. **Prohibidos los efectos secundarios en `__init__.py`:** Los paquetes expuestos como dependencia cruzada (`shared-pkg` y cualquier paquete de `metrics-api`) **no pueden tener efectos secundarios en su `__init__.py`**. Cualquier inicialización (conexión a base de datos, APIs, variables globales de estado) debe quedar detrás de una función o clase explícita. El paquete debe ser importable instantáneamente para no ralentizar el arranque en caliente de procesos como `metrics-worker`.

## 5. Tabla de Dependencias de Código Cruzadas

| Dirección | Módulo/función | Motivo | Versión fijada | Fecha | Procedimiento de rollback |
|-----------|----------------|--------|----------------|-------|---------------------------|
| `llm-wiki-assistant` -> `bdc-trazabilidad` | `shared-pkg.okf_contract` | Extraer strings mágicas (mensajes de commit y rutas) para parseo de eventos de log e ingestión OKF sin acoplar la lógica completa de Git. | `1.0.0` | 2026-08-13 | Revertir el uso de `shared-pkg.okf_contract` en `metrics-worker/worker.py` y restaurar variables hardcodeadas locales. |

## 6. Pruebas de Integración y Compatibilidad Cruzada (CI/CD)

Para garantizar la integridad del sistema multi-repositorio, la Fase 1 estableció verificaciones de CI/CD simuladas pero funcionales para evitar roturas accidentales entre `bdc-trazabilidad` y `llm-wiki-assistant`:

### Matriz de Compatibilidad (Cross-Repo Test)
#### 2. Workflow cruzado en bdc-trazabilidad (GitHub Actions real)
El repositorio consumidor (`bdc-trazabilidad`) cuenta con un pipeline en GitHub Actions (`.github/workflows/ci.yml`) que actúa como receptor del evento.
Mediante el trigger `on: repository_dispatch` (tipo `cross-repo-test`), el pipeline se activa instantáneamente tras el éxito del proveedor.
Utiliza el payload del evento (`client_payload.version`) para hacer un *checkout* de la revisión exacta del código del proveedor, asegurando que las pruebas de compatibilidad (`scripts/test_compat_matrix.sh`) se ejecuten contra los cambios específicos, todo orquestado a través del runner de GitHub Actions de forma 100% nativa.

### Detección de Ciclos de Dependencia
El script `scripts/detect_cycles.sh` en `bdc-trazabilidad` analiza el grafo de dependencias declaradas entre los módulos durante la ejecución normal del pipeline CI.
- **Caso OK:** Grafo acíclico, el CI continúa.
- **Caso FAIL:** Si se detecta un ciclo (ej. A -> B -> A), el script fuerza un exit code `1`, abortando el pipeline tempranamente con un mensaje explícito que identifica el ciclo detectado.

---

## 7. Regla de Migraciones de Base de Datos Estrictamente Aditivas

Ninguna migración de Alembic ya aplicada (es decir, ya mergeada en la rama principal) se edita retroactivamente. Todo cambio de esquema, incluyendo correcciones, se implementa como una migración nueva.

- La migración `catalogo_conceptos` (Fase 2 v3) es el ejemplo canónico: añade la tabla `conceptos` y recrea `conceptos_detectados` con FK real sin tocar la migración `baseline`.
- Ver detalles completos en [`docs/esquema-metrics.md`](./esquema-metrics.md).

---

## 8. Estado de la Fase 2 — Esquema de Base de Datos

**Estado: Completada (validación de dominio diferida, no bloqueante)**

La implementación técnica está completa: cinco tablas en `metrics`, migraciones reversibles verificadas (`upgrade`/`downgrade`/`upgrade`), aislamiento de esquema verificado con `\dn+ public`, suite de tests en verde.

### Cambio de criterio respecto al plan maestro original

La reunión bloqueante con el profesorado para validación de dominio **no va a celebrarse en el corto plazo**. Por decisión explícita del equipo, esa validación queda **diferida**, no bloqueante. El esquema se declara utilizable en producción bajo esa condición, apoyado en las mejoras de modularidad de la Fase 2 v3 (catálogo de conceptos, repositorio, política JSONB) para que la validación futura pueda incorporarse vía migraciones aditivas sin reescritura destructiva.

### Riesgos conocidos que quedan sin resolver

1. Posibles campos de `metadatos` que deberían ser columnas y no se han identificado aún (sin casos de uso validados con profesorado).
2. El catálogo de `conceptos` existe pero está vacío — la población real contra los `AGENTS.md` de cada curso es trabajo pendiente de Fase 3.
3. `eventos_sync` no tiene `moodle_user_id`/`moodle_course_id`; pendiente confirmar si el dashboard necesitará filtrar eventos por alumno/curso directamente.

### Punto RGPD — no negociable, independiente de esta decisión

El punto 9.4 del plan maestro (revisión RGPD/LOPD con servicios jurídicos de la UGR) sigue siendo un **hito bloqueante de lanzamiento a producción real con datos de alumnos**. Diferir la validación de dominio con profesorado **no difiere el cumplimiento RGPD**.

Ver documentación completa del esquema en [`docs/esquema-metrics.md`](./esquema-metrics.md).

---

## 9. Estado de la Fase 6.5 — Auditoría de GitHub (Reconciliación)

**Estado: Completada**

Se ha integrado el trabajador `worker.py` en `metrics-worker` para monitorizar y reconciliar los eventos procedentes de GitHub. 
Se ha descartado la premisa original del plan de usar una base de datos SQLite por-alumno para el buffer local del bot. 

### Arquitectura de Reconciliación en 2 Capas (Bucles)

1. **Bucle 1 (Feed Consumer - Capa 1):** Un ciclo de alta frecuencia (`POLL_INTERVAL_SEC` = 30s) que hace `GET /eventos-recientes` sobre `mapeo-api` para sincronizar eventos rápidamente en `eventos_sync` (vía ingesta rápida originada en el POST del bot, que preserva el buffer `.jsonl` como red de seguridad).
2. **Bucle 2 (Reconciliación/Auditor - Capa 2):** Un ciclo de baja frecuencia (`RECONCILIATION_INTERVAL_SEC` = 1 día) que verifica proactivamente cada fork en la API de GitHub para asegurar que todos los commits reales del historial de GitHub existen en `eventos_sync`. Si falta alguno, se genera una `DiscrepanciaAuditoria`.

**Decisiones Clave de Diseño y Límites (Rate Limit):**
- El intervalo de 1 día (86400s) está justificado estrictamente por el límite de 5000 peticiones/hora de la API autenticada de GitHub, considerando el paginado del historial para N forks de estudiantes. Modificar esta frecuencia en el futuro requerirá recalcular el presupuesto de peticiones.
- El POST a `/eventos` reportado por el bot siempre va atado al `commit_sha` real, permitiendo trazar 1 a 1 la interacción desde el bot hasta el histórico del repositorio.
- Las tablas residen físicamente en `mapeo_db` y el worker se conecta por conexión de red interna Docker. 

**Cumplimiento LOPD/RGPD**: 
Dado que el worker audita directamente sobre los forks en la organización GitHub docente, se reitera que el acceso debe limitarse a la organización formal autorizada de la UGR y debe evaluarse frente al punto 9.4 del plan maestro antes de producción.

---

## 10. Arquitectura de Integración Final (End-to-End)

**Estado: Completada**

El flujo End-to-End (E2E) consolidado integra Moodle, Matrix (Synapse/Maubot), y los paneles de control de métricas bajo la siguiente arquitectura definitiva:

1. **Aprovisionamiento desde Moodle:** 
   El plugin `block_bdc` en Moodle es el punto de entrada. Al pulsar "Sincronizar", Moodle llama a `mapeo-api` para asegurar la creación del repositorio GitHub del estudiante y crear una sala de chat en Matrix (`Synapse Admin API`). Esto garantiza que solo los estudiantes formalmente matriculados dispongan de entorno.
2. **Autojoin del Bot (Matrix):** 
   Se utiliza la funcionalidad nativa de autojoin de Maubot a nivel de cliente (configurada directamente en la instancia de Maubot) en lugar de eventos de invitación a nivel de código de plugin, garantizando la estabilidad y evitando errores de tipos de eventos (`ROOM_INVITE` inexistente).
3. **Flujo de Interacciones:** 
   El asistente (Maubot `llm_wiki_bot`) escucha en las salas conectadas. Al recibir interacción de un estudiante, procesa el documento, sincroniza el estado a GitHub (`push`) y paralelamente reporta el evento estructurado a la API de mapeos, la cual asienta el registro en `metrics.interacciones`.
4. **Seguridad y Aislamiento en el Dashboard:** 
   `bdc-trazabilidad` requiere inicio de sesión. Utiliza tokens JWT generados contra Moodle para validar la identidad y extrae los `allowed_courses` (cursos donde el profesor tiene docencia) desde `mapeo-api`. El backend (`metrics-api`) restringe de forma estricta (`auth.py`) que el usuario únicamente pueda solicitar y visualizar datos de `metrics.interacciones` para los cursos a los que está autorizado, asegurando un aislamiento total entre profesores y estudiantes.

### Limitaciones Conocidas del Test True-E2E
Para la validación automatizada de este flujo en entornos de Integración Continua (la suite `True-E2E`), **existe una limitación intencionada en el alcance de la prueba:** el orquestador simula el comportamiento a partir de la llamada `POST /eventos` hacia `mapeo-api`, asumiendo que el Bot ya ha detectado la actividad en Matrix. No se levanta ni se verifica el clúster de Matrix/Synapse/Maubot durante este test específico, ya que hacerlo añadiría un grado de inestabilidad y sobrecarga arquitectónica incompatible con las pruebas automatizadas de CI de la API. El tramo anterior (Matrix -> Maubot) se asume verificado por componentes individuales.

---

## 11. Excepciones de Documentación (Doxygen)

Como regla general del proyecto (desde la Fase 0.1), Doxygen corre en modo estricto (`WARN_AS_ERROR = YES`) para evitar deuda técnica en la documentación.

**Excepción Aprobada (Fase 8):**
Se ha relajado explícitamente la directiva `WARN_IF_UNDOCUMENTED = NO` en el `Doxyfile` de `bdc-trazabilidad`. Esta excepción técnica se aprueba para evitar la desproporcionada carga de requerir un docstring individual para *cada campo y variable interna* de los modelos de validación Pydantic en `metrics-api/schemas.py`. 
- Esta regla aplica únicamente a la exigencia de documentación miembro-por-miembro. 
- La directiva `WARN_AS_ERROR = YES` se mantiene activa para capturar errores de sintaxis, conflictos de parsing y enlaces rotos.
