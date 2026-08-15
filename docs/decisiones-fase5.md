# Decisiones de Diseño: Fase 5 (Autenticación y Autorización)

## Decisión 1: Replicar llamada HTTP a Moodle vs Importar `rest_auth_provider.py`

Se ha decidido **replicar** la llamada HTTP hacia Moodle (`blocks/bdc/api/auth.php`) para validar las credenciales de los usuarios en lugar de importar el módulo de autenticación existente en `llm-wiki-assistant` (`rest_auth_provider.py`).

**Justificación de Seguridad:**
A primera vista, replicar código podría parecer que contraviene la filosofía de DR (Don't Repeat) y crea riesgo de divergencia. Sin embargo:
1. **La validación real vive en Moodle:** Ni el `mapeo-api`, ni Matrix Synapse, ni `metrics-api` validan contraseñas por sí mismos. Simplemente delegan esta responsabilidad enviando un JSON con las credenciales al endpoint `api/auth.php` de Moodle, que es la única fuente de verdad real de identidades.
2. **Cero divergencia:** Al replicar únicamente la petición HTTP cliente hacia el mismo endpoint de Moodle, se mitiga de base el riesgo de divergencia de validación. La validación se comporta de la misma manera exacta en todos los sistemas.
3. **El acoplamiento de `rest_auth_provider.py`:** El archivo en `llm-wiki-assistant` es un proveedor de autenticación diseñado específicamente para Matrix Synapse. Contiene lógica para lidiar con el formato de IDs de Matrix (`@user:localhost`) y la auto-creación de usuarios en la base de datos de Synapse usando la API interna (`self.api.check_user_exists`). Importar esto como paquete versionado en `metrics-api` requeriría refactorizaciones pesadas para abstraer esta lógica y modificar las dependencias del contenedor de Synapse, introduciendo gran complejidad operativa y poniendo en riesgo el funcionamiento actual del sistema por ahorrarnos una simple llamada a la librería de HTTP.

## Decisión 2: Alcance del Log de Auditoría (Append-Only)

El sistema mantendrá un registro en `metrics_db.auditoria_accesos` con garantía "append-only" real, soportada por un Trigger a nivel de la base de datos que bloquea de forma incondicional cualquier `UPDATE` o `DELETE` sobre la tabla. 

**Alcance del log:**
Se registrarán en esta tabla **tanto fallos de autorización (403) como fallos de autenticación (401 / 500 derivados de la auth)**. El motivo es que un patrón de múltiples intentos fallidos contra la misma cuenta (fuerza bruta o credenciales comprometidas) es una señal crítica de seguridad que el sistema universitario debe auditar.

**Regla estricta de persistencia (RGPD / Privacidad por Diseño):**
Bajo ninguna circunstancia se persistirán contraseñas ni la cadena completa del token JWT en la tabla de auditoría, ni de manera separada ni dentro de ningún campo JSON (metadatos).
- **En caso de intento fallido contra Moodle:** Se registrará el `usuario` enviado, el `timestamp` y el `resultado` (por ejemplo, "Credenciales inválidas"). La contraseña jamás se persistirá.
- **En caso de firma inválida o JWT manipulado:** Se registrarán los metadatos recuperables, como la IP origen o el `timestamp`, pero nunca el JWT en sí.

Si se violara esta regla, se crearía de inmediato un agujero de seguridad severo por persistir material secreto en texto plano. Debido a la naturaleza inmutable (append-only) de esta tabla, un error de diseño aquí no podría revertirse sin intervención manual extraordinaria sobre la base de datos de producción. Por ello se exige como regla crítica de diseño de esta fase.

## Decisión 3: Expiración del JWT y Mecanismo de Refresh

**Expiración corta:** Se ha configurado el JWT con una expiración corta y estricta de **15 minutos**. Dado el nivel de riesgo de esta fase (potencial exposición de datos entre alumnos), un tiempo de vida corto reduce la ventana de oportunidad en caso de que un token sea comprometido, exfiltrado o robado.

**Sin mecanismo de Refresh:** Se ha decidido **NO implementar** un mecanismo de "Refresh Token". 
- **Justificación:** La complejidad de implementar un esquema seguro de rotación de refresh tokens (almacenamiento seguro, invalidación y listas de revocación) excede el beneficio esperado en esta fase. 
- **Mitigación:** En caso de que el token expire, el frontend de los profesores y alumnos simplemente deberá solicitar al usuario que vuelva a autenticar contra Moodle (o hacerlo automáticamente de manera silenciosa si el frontend ya tiene una sesión Moodle activa, dado que Moodle y metrics-api comparten el flujo delegado). Esto prioriza la simplicidad y robustez de la seguridad por encima de la conveniencia de una sesión ininterrumpida.

## Decisión 4: Eliminación total del token estático heredado (`METRICS_API_TOKEN`)

Durante el desarrollo de la Fase 4, se implementó temporalmente una autenticación rudimentaria en `metrics-api` basada en un token estático transmitido en los headers (`METRICS_API_TOKEN`). 

Se ha decidido **eliminar por completo** este mecanismo en la Fase 5. 
- **Justificación:** Permitir que ambos mecanismos coexistan generaría confusión, incrementaría la superficie de ataque y provocaría ambigüedad en auditorías de seguridad futuras sobre cuál es el mecanismo de autorización real.
- **Estado actual de los tests:** Los 4 tests originales del archivo `test_auth.py` (que verificaban el funcionamiento del token estático) han mantenido sus nombres genéricos (`test_auth_no_token`, `test_auth_invalid_token`, `test_auth_valid_token`, etc.), pero su implementación interna ha sido **reescrita por completo** para probar exclusivamente la nueva validación JWT delegada a Moodle. El antiguo token ya no existe como mecanismo válido en el middleware de autenticación (`verificar_token`).
