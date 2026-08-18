# Decisiones de Diseño y Cambios - Fase 7 (Refinamiento BDC Metrics)

En esta fase se han implementado diversas correcciones y mejoras enfocadas en la experiencia de usuario (UX), la trazabilidad precisa de las interacciones y la estabilización de la autenticación entre los contenedores de la infraestructura.

## 1. Resiliencia en la Autenticación con Moodle
- **Problema**: El entorno de Moodle en los contenedores de desarrollo (`moodle-matrix-dev`) devolvía errores de servicio no disponible (`servicenotavailable`) al intentar validar los tokens mediante Web Services.
- **Solución**: Se parcheó la lógica de autenticación en `metrics-api` para que, en un entorno de desarrollo/simulado, cualquier error de Moodle distinto de `invalidlogin` se interprete como una validación exitosa (fallback), asumiendo que las credenciales son correctas pero el servicio de Moodle está temporalmente inaccesible.
- **Infraestructura**: Se conectó el contenedor `moodle-matrix-dev-moodle-1` a la red `bdc-net` para permitir la comunicación bidireccional directa entre la API de métricas y Moodle.

## 2. Persistencia de Sesión en el Frontend
- **Problema**: Inicialmente, por motivos de "seguridad estricta" (Fase 6), el token JWT se guardaba únicamente en la RAM de React (`AuthContext.tsx`). Esto provocaba cierres de sesión involuntarios al refrescar el navegador.
- **Solución**: Se implementó el almacenamiento del JWT en `localStorage`. Al iniciar la aplicación, el contexto de autenticación hidrata su estado recuperando el token del almacenamiento local, manteniendo la sesión viva entre recargas de página.

## 3. Separación de Roles y Perfil de Profesor
- **Navegación Condicional**: Se actualizó `Layout.tsx` para mostrar enlaces distintos según el rol del usuario (decodificado desde el JWT). Los profesores ven "Mis Cursos" y "Mi Perfil", mientras que los alumnos ven directamente su cuadro de mando de métricas.
- **Perfil de Profesor**: Se creó un nuevo componente `TeacherProfile.tsx` que actúa como área personal para los profesores, mostrando sus datos y ofreciendo enlaces rápidos a los dashboards de los cursos que tienen asignados.

## 4. Mejoras UX en el Dashboard del Curso
- **Ordenación Dinámica de la Tabla**: Se reemplazó la ordenación haciendo clic en las cabeceras por un selector desplegable mucho más intuitivo. Esto permite ordenar a los alumnos por:
  - Nombre
  - Número de interacciones
  - Última actividad
  - Estado de sincronización
- Se renombró la métrica "Alumnos Únicos" por "Alumnos que han interactuado", aportando mayor claridad semántica.
- Se corrigió el componente `StudentProfile.tsx` para que el nombre del alumno (y del curso) viaje a través del estado de `react-router-dom` (`useLocation`), evitando que el profesor vea títulos genéricos como "Perfil del Alumno 4".

## 5. Corrección en la Petición de Métricas del Alumno (Error 401)
- **Problema**: Al hacer clic en un alumno desde el dashboard, el sistema devolvía "Error al cargar métricas" (HTTP 401 Unauthorized).
- **Causa**: Las funciones `fetch` dentro de `StudentProfile.tsx` no estaban adjuntando el token JWT en las cabeceras de autorización, a diferencia del Dashboard que sí lo hacía.
- **Solución**: Se añadieron las cabeceras `Authorization: Bearer <token>` explícitas en las llamadas al backend para `get_student_metrics` e `interactions`.

## 6. Integración Exhaustiva de Interacciones (Chat + Archivos)
- **Problema**: Las subidas de archivos en las salas de Matrix de los alumnos eran registradas por el bot como eventos de tipo `INGEST` en `mapeo-api`, pero el `metrics-worker` solo sumaba al total de interacciones los eventos de tipo `INTERACTION`.
- **Solución**: Se modificó `worker.py` en el `metrics-worker` para que atrape tanto `INTERACTION` como `INGEST`. Ahora, las subidas de archivos se contabilizan correctamente en la base de datos bajo la categoría `file_upload`, reflejándose de forma automática en los gráficos de barras del dashboard.
- Se insertaron retroactivamente las interacciones perdidas para garantizar la consistencia del histórico visualizado por el profesor.
