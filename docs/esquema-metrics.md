# Esquema de Base de Datos: `metrics`

Este documento complementa `docs/integracion-bdc.md` con las decisiones
de diseño específicas del esquema `metrics` de `bdc-trazabilidad`.

## Estado del esquema

**Fase 2 completada — validación de dominio diferida, no bloqueante**

La implementación técnica del esquema está completa y verificada:
cinco tablas en el esquema `metrics` (`interacciones`, `conceptos`,
`conceptos_detectados`, `eventos_sync`, `reversiones`), migraciones
reversibles con Alembic, aislamiento de esquema verificado, y suite de
tests en verde.

La validación formal con el equipo docente (profesorado) queda **diferida**
por decisión explícita del equipo — no hay una reunión bloqueante en el
corto plazo. El esquema se declara utilizable en producción bajo esa
condición, apoyado en las mejoras de modularidad de la Fase 2 (v3) para
que la validación futura pueda incorporarse vía migraciones aditivas sin
reescritura destructiva.

### Riesgos conocidos documentados

Los siguientes puntos quedan sin resolver por la ausencia de validación
de dominio. No son bloqueos técnicos ahora mismo, pero deben revisarse
antes de considerar el esquema como definitivo:

1. **Campos de `metadatos` no identificados:** Es posible que haya claves
   dentro del campo JSONB `metadatos` de `interacciones` que deberían ser
   columnas reales (porque se consultarán con frecuencia), pero que aún no
   se han identificado porque no hay casos de uso concretos validados con
   el profesorado. Ver la Política de Promoción más abajo.

2. **Catálogo de `conceptos` vacío:** La tabla `conceptos` existe con la
   estructura correcta (nombre + curso_id, con índice único compuesto),
   pero no tiene datos. La población real contra los `AGENTS.md` de cada
   curso queda diferida (sin fase asignada todavía — depende de disponer 
   de repositorios de curso reales con `AGENTS.md`, o de un mecanismo 
   como un posible endpoint de Fase 4 para que alguien externo lo pueble 
   manualmente). Hasta entonces, `conceptos_detectados` no puede 
   referenciar conceptos reales.

3. **`eventos_sync` sin `moodle_user_id`/`moodle_course_id`:** No está
   confirmado si el dashboard necesitará filtrar eventos de sincronización
   por alumno o por curso directamente. Si lo necesita, habrá que añadir
   esas columnas mediante una migración aditiva en Fase 3/4.

### Punto RGPD — no negociable

El punto 9.4 del plan maestro (revisión RGPD/LOPD con los servicios
jurídicos de la UGR) sigue siendo un **hito bloqueante de lanzamiento a
producción real con datos de alumnos**, independiente de la decisión de
diferir la validación de dominio con el profesorado. Diferir la validación
de dominio **no difiere el cumplimiento RGPD**. El sistema no puede
procesar datos reales de alumnos hasta que esa revisión se haya completado.

---

## Tablas del esquema `metrics`

### `interacciones`

Registro principal de cada interacción de un alumno con el sistema LLM.

| Columna | Tipo | Restricciones | Notas |
|---|---|---|---|
| `id` | UUID | PK | Generado en aplicación |
| `timestamp` | DateTime | índice | |
| `moodle_user_id` | Integer | not null, índice | FK lógica hacia mapeo-api |
| `moodle_course_id` | Integer | not null, índice | FK lógica hacia mapeo-api |
| `tipo_interaccion` | String | not null | |
| `referencia_evento` | String | nullable | |
| `metadatos` | JSONB | nullable | Zona de aterrizaje provisional |

### `conceptos`

Catálogo normalizado de conceptos pedagógicos por curso.

| Columna | Tipo | Restricciones | Notas |
|---|---|---|---|
| `id` | UUID | PK | |
| `nombre` | String | not null | |
| `curso_id` | Integer | not null | FK lógica; unicidad compuesta con `nombre` |

Índice único: `(curso_id, nombre)` — evita duplicados dentro del mismo curso.

### `conceptos_detectados`

Asociación entre una interacción y un concepto del catálogo.

| Columna | Tipo | Restricciones | Notas |
|---|---|---|---|
| `id` | UUID | PK | |
| `interaccion_id` | UUID | FK → interacciones.id, CASCADE | |
| `concepto_id` | UUID | FK → conceptos.id, RESTRICT | No se puede borrar un concepto si tiene detecciones |

### `eventos_sync`

Eventos de sincronización entre sistemas.

| Columna | Tipo | Restricciones | Notas |
|---|---|---|---|
| `id` | UUID | PK | |
| `timestamp` | DateTime | índice | |
| `tipo_evento` | String | not null | |
| `estado` | String | not null | |
| `resultado` | JSONB | nullable | |

### `reversiones`

| Columna | Tipo | Restricciones | Notas |
|---|---|---|---|
| `id` | UUID | PK | |
| `interaccion_id` | UUID | FK → interacciones.id, CASCADE | |
| `timestamp` | DateTime | índice | |

---

## Política de Promoción de Campos JSONB a Columnas

El campo `metadatos` (JSONB) en `interacciones` es una zona de aterrizaje
provisional para campos cuya necesidad de estructuración no está aún
confirmada. Esta política define cuándo y cómo promover una clave de ese
JSONB a columna real:

**Condición de promoción:** cualquier clave dentro de `metadatos` que
empiece a consultarse de forma frecuente — por ejemplo, usarse como filtro
(`WHERE metadatos->>'clave' = valor`) o como eje de agregación en un
endpoint — debe promoverse a columna real mediante una migración aditiva
de Alembic.

**Señales que indican que es hora de promover:**
- La clave aparece en más de un endpoint o query distinta.
- Se crea un índice sobre esa clave en el JSONB (señal de que ya es un
  campo de primera clase en la práctica).
- El tipo de dato importa (ej. se quiere ordenar numéricamente o comparar
  fechas y el JSONB lo trata como string).

**Procedimiento:**
1. Crear una migración nueva (nunca editar la baseline ni ninguna
   migración ya mergeada) que añada la columna con `ALTER TABLE ... ADD COLUMN`.
2. Backfill de los datos existentes desde `metadatos` hacia la nueva columna.
3. Una vez validado el backfill, la clave puede eliminarse del JSONB
   opcionalmente (otra migración separada, nunca la misma).
4. Actualizar `models.py` y este documento.

**Lo que no debe pasar:** que una clave de `metadatos` sea de facto un
campo de negocio usado en queries sin pasar nunca por este proceso. Si hay
duda, abrir una issue antes de añadir la query.

---

## Regla de Migraciones Estrictamente Aditivas

Ninguna migración de Alembic ya aplicada (es decir, ya mergeada en la rama
principal) se edita retroactivamente. Todo cambio de esquema, incluyendo
correcciones de errores en migraciones anteriores, se implementa como una
migración nueva.

**Ejemplo de aplicación:** la migración `catalogo_conceptos` (Fase 2 v3)
no modifica la migración `baseline` existente — crea una nueva revisión que
añade la tabla `conceptos` y recrea `conceptos_detectados` con la FK real.

**Excepción única permitida:** editar una migración antes de que haya sido
mergeada (es decir, mientras está en revisión de PR y aún no se ha aplicado
en ningún entorno compartido).
