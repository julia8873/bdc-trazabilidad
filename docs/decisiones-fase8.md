# Decisiones de Diseño y Cambios - Fase 8

Este documento recoge las decisiones técnicas implementadas durante la Fase 8 en el ecosistema del panel de métricas (`bdc-trazabilidad`).

## 1. Flexibilización de Doxygen (Pydantic Models)
- **Problema**: El modo estricto de Doxygen (`WARN_AS_ERROR = YES` y `WARN_IF_UNDOCUMENTED = YES`) impedía compilar la documentación exitosamente porque exigía escribir un docstring individual para *cada campo y variable interna* de los modelos de validación de datos (Pydantic) en `metrics-api/schemas.py`.
- **Decisión**: Se aprobó una excepción técnica relajando la directiva a `WARN_IF_UNDOCUMENTED = NO` en el `Doxyfile` de `bdc-trazabilidad`.
- **Justificación**: Añadir docstrings a campos auto-explicativos de modelos Pydantic aportaba poco valor semántico frente a la alta carga de mantenimiento (deuda técnica).
- **Seguridad**: La directiva `WARN_AS_ERROR = YES` se mantiene activa para seguir deteniendo la compilación ante errores reales de sintaxis, conflictos de parsing o enlaces rotos en el Markdown.
