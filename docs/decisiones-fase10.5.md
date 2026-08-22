# Fase 10.5 - Consideraciones Futuras sobre la Extracción de Conceptos

Durante la implementación de la Fase 10.5 (Extracción de Conceptos por Intercambio y Vista de Conversaciones del Perfil de Alumno), se tomó la decisión explícita de realizar **dos commits separados** para registrar una única interacción en el repositorio del alumno:

1. El primer commit guarda el texto literal de la interacción (preguntas y respuestas) en la bitácora bajo `logs/interacciones/`.
2. El segundo commit, con el mensaje especial `[bot] okf: conceptos extraidos de interaccion`, guarda los conceptos extraídos por el LLM en la carpeta `okf/entities/`.

## Motivos de la decisión
- Mantener el historial de Git limpio y modular, separando lo que es "registro bruto" (log) de lo que es "análisis derivado" (conceptos).
- Minimizar el riesgo de conflictos al guardar en distintas áreas lógicas del repositorio (bitácora vs entidades).
- Facilitar la trazabilidad: el endpoint de lectura puede consultar de forma aislada las rutas.

## Cosas a tener en cuenta en un futuro
- Si el volumen de interacciones crece de manera masiva, la creación de dos commits por cada mensaje podría sobrecargar el historial de Git del repositorio del alumno o los límites de la API de GitHub al realizar el push.
- Si en un futuro se requiere atenuar la carga de operaciones en Git, se debe considerar unificar ambos registros (log y conceptos) en un único commit por interacción, o bien procesar los commits en batches (procesamiento por lotes periódico en lugar de síncrono al mensaje).
- La Capa 2 de reconciliación en `metrics-worker` ignora específicamente el mensaje de commit de los conceptos para no generar ruido de discrepancia, por lo que cualquier cambio en la nomenclatura de los commits deberá reflejarse de forma estricta en el contrato OKF y en la Capa 2.
