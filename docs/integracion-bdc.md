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
- **CI/CD Compartido:** Se utiliza un workflow reutilizable (`.github/workflows/deploy-reusable.yml`) alojado en `llm-wiki-assistant`, que es invocado desde los pipelines de `bdc-trazabilidad` para centralizar la lógica de despliegue. Adicionalmente, el pipeline de `bdc-trazabilidad` incluye un paso de validación cruzada y detección de ciclos (actualmente en modo placeholder) que disparará los tests de `llm-wiki-assistant` cuando existan dependencias de código reales (Fases 3 y 5).
- **Reversión:** Para revertir el acoplamiento de infraestructura, se debe:
  1. Eliminar la directiva `include:` de `bdc-trazabilidad/deploy/docker-compose.prod.yml`.
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
- El repositorio consumidor fijará la versión exacta en su sistema de gestión de dependencias (por ejemplo, en requirements.txt o poetry). Nunca se apuntará a la rama `main` o ramas en desarrollo activo.

## 5. Tabla de Dependencias de Código Cruzadas

| Dirección | Módulo/función | Motivo | Versión fijada | Fecha | Procedimiento de rollback |
|-----------|----------------|--------|----------------|-------|---------------------------|
|           |                |        |                |       |                           |

*(Esta tabla se rellenará en futuras fases conforme se implementen dependencias cruzadas reales).*

## 6. Pruebas de Integración y Compatibilidad Cruzada (CI/CD)

Para garantizar la integridad del sistema multi-repositorio, la Fase 1 estableció verificaciones de CI/CD simuladas pero funcionales para evitar roturas accidentales entre `bdc-trazabilidad` y `llm-wiki-assistant`:

### Matriz de Compatibilidad (Cross-Repo Test)
Si un paquete o componente compartido se modifica en el repositorio proveedor (`llm-wiki-assistant`), su pipeline CI dispara un evento `repository_dispatch` (tipo `cross-repo-test`) hacia el repositorio consumidor (`bdc-trazabilidad`). 
El consumidor ejecuta inmediatamente su suite de tests contra la nueva versión (validado con el script `scripts/test_compat_matrix.sh`). 
- **Caso OK:** Si los tests pasan, el CI valida la compatibilidad.
- **Caso FAIL:** Si la nueva versión introduce *breaking changes*, los tests fallan y el CI del consumidor notifica o bloquea, previniendo que la regresión llegue a producción.

### Detección de Ciclos de Dependencia
El script `scripts/detect_cycles.sh` en `bdc-trazabilidad` analiza el grafo de dependencias declaradas entre los módulos durante la ejecución normal del pipeline CI.
- **Caso OK:** Grafo acíclico, el CI continúa.
- **Caso FAIL:** Si se detecta un ciclo (ej. A -> B -> A), el script fuerza un exit code `1`, abortando el pipeline tempranamente con un mensaje explícito que identifica el ciclo detectado.
