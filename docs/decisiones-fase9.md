# Decisiones de Diseño y Cambios - Fase 9

Este documento recoge las decisiones técnicas implementadas durante la Fase 9 en el ecosistema del panel de métricas (`bdc-trazabilidad`).

## 1. Versionado de la API (v1)
- **Problema**: A medida que el ecosistema y los consumidores crecen (Moodle, Frontend Dashboard, Workers), cambiar las estructuras de datos de la API rompía la retrocompatibilidad.
- **Decisión**: Se implementó un esquema de versionado en las rutas públicas de `mapeo-api` y `metrics-api`, quedando todas bajo el prefijo `/v1/`.
- **Manejo de Transición**: Las rutas antiguas (sin prefijo) no se eliminaron de inmediato. Se han conservado como **alias deprecados**, devolviendo una cabecera HTTP estándar de fin de vida (`Sunset: Wed, 18 Feb 2027 00:00:00 GMT`), dando 6 meses de margen para actualizar los consumidores antiguos.

## 2. Centralización de Tiempos y Configuración Compartida
- **Problema**: El worker (`metrics_worker`) tenía variables de tiempo y comportamiento hardcodeadas directamente en su código Python, lo que obligaba a recompilar la imagen Docker para cualquier ajuste de latencia o reintentos.
- **Decisión**: Se refactorizó la lógica en `worker.py` (validado mediante `test_no_hardcoded_timings.py`) para que recupere dinámicamente sus tiempos y métricas base del archivo transversal `config.yaml`.
- **Justificación**: Unifica los tiempos de sincronización del worker con las reglas dictadas por el orquestador principal, evitando discrepancias de tiempo de espera y centralizando la configuración general.
