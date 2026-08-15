# Decisiones de Diseño: Fase 6 (Frontend Dashboard)

## Decisión 1: Framework de Frontend (Vite + React vs Next.js)

Aunque el plan maestro original sugería el uso de Next.js, se ha decidido optar por **Vite + React (SPA puro)**.

**Justificación:**
1. **Naturaleza del Dashboard:** La aplicación es un dashboard de métricas 100% autenticado. No existe contenido público, por lo que las capacidades de Server-Side Rendering (SSR) o Static Site Generation (SSG) que ofrece Next.js no aportan valor real y, por el contrario, añaden una capa innecesaria de complejidad en el servidor (Node.js backend para el frontend).
2. **SEO Irrelevante:** Al estar detrás de un login estricto, no hay requerimientos de indexación por motores de búsqueda.
3. **Simplicidad Operativa:** Un proyecto Vite genera un bundle estático (HTML/CSS/JS) que puede ser servido de forma trivial por cualquier servidor web ligero (como Nginx o Caddy) o un bucket S3, encajando mejor con la simplicidad de infraestructura del stack actual.

## Decisión 2: Patrón de Almacenamiento del JWT

Se ha decidido **almacenar el JWT de sesión estrictamente en la memoria de la aplicación (React State/Context)**, rechazando el uso de `localStorage` o `sessionStorage`.

**Justificación y Trade-offs:**
- **Seguridad (Mitigación XSS):** Al no persistir el token en el almacenamiento del navegador, cualquier script malicioso (XSS) inyectado pierde la capacidad de robar el token de forma pasiva tras recargar la página.
- **Trade-off de UX:** El precio de esta seguridad es que si el usuario recarga la página por completo (F5), el estado de memoria se limpia y el usuario es deslogueado instantáneamente. 
- **Restauración de ruta:** Para mitigar el impacto de un login forzado, si el usuario recibe un 401 (o pierde sesión) se guardará temporalmente **únicamente la ruta de la URL** (ej. `/course/1/student/2`) en el estado del enrutador o en `sessionStorage` para redirigirlo de vuelta tras el login. **Ningún dato del curso, alumno o token será persistido**.

## Decisión 3: Visualización de Percentiles con Muestras Pequeñas

El backend calculará los percentiles usando `percentile_cont()` en PostgreSQL agrupando el `total_interactions` por `moodle_user_id`.

**Tratamiento de Muestras Pequeñas (UX):**
Si un curso tiene menos de 5 alumnos con interacciones registradas, los cuartiles estadísticos carecen de significancia real y pueden inducir a error. 
- **Decisión:** El frontend verificará la cantidad de alumnos únicos (o un flag del backend). Si la muestra es insuficiente, la sección de percentiles se ocultará o mostrará un estado vacío explícito: *"Datos insuficientes para el cálculo de percentiles (se requieren al menos 5 alumnos interactuando)"*, mostrando únicamente las medias o totales.

## Decisión 4: Transparencia en Origen de Directrices (IA vs Proyecto)

Se acuerda establecer un precedente explícito para el resto del proyecto: si en algún momento futuro se detecta un conflicto entre las directrices base del agente (ej. preferencias de UI como Glassmorphism o Tailwind) y los requisitos funcionales del proyecto, el agente deberá identificar y reportar explícitamente el origen de dicha directriz.

**Justificación:**
- Garantiza que las decisiones de diseño y arquitectura estén guiadas únicamente por el contexto real del proyecto (en este caso, usabilidad para profesorado no técnico) y no por sesgos o "defaults" internos del modelo.
- Mejora la transparencia y previene desviaciones sutiles que requieran correcciones en fases posteriores.
