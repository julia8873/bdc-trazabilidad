# metrics-api

Este directorio contendrá el servicio FastAPI para el dashboard de trazabilidad y métricas. 
Se implementará su contenido funcional en la Fase 2.

## Limitaciones y Decisiones de Diseño

### Rotación de Claves PII (PII_SECRET_KEY)
En esta versión, el `PII_SECRET_KEY` utilizado para cifrar los valores originales de PII en la tabla `pii_vault` (cifrado a nivel de aplicación con Fernet) **no soporta rotación automática**. 

**Decisión documentada:** Dado que la política de retención elimina (purga) físicamente la PII a los 90 días mediante un job programado, el periodo de exposición es acotado temporalmente. Implementar un mecanismo completo de rotación de claves (con versionado de claves, re-cifrado de datos en segundo plano y gestión múltiple de secretos) añade una complejidad significativa que excede los requisitos de esta primera versión. Si la clave se viera comprometida, el impacto se limita a los datos retenidos de los últimos 90 días que no hayan sido purgados.
