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

- **Costura de Orquestación:** Este fichero utiliza la directiva `include:` de Docker Compose para integrar los servicios de `llm-wiki-assistant` (referenciados mediante ruta relativa `../llm-wiki-assistant/`).
- **Reversión:** Para revertir el acoplamiento de infraestructura, basta con eliminar la directiva `include:` y gestionar los servicios de este repo de forma totalmente autónoma.
- ⚠️ **Aviso Explícito:** Si revertir cualquier acoplamiento (de infraestructura o de código) requiere modificar más código o configuración de lo estrictamente necesario, es señal de que se implementó de forma incorrecta y debe ser refactorizado inmediatamente.

*(Nota: En la validación inicial de Fase 0 v3, el fichero `llm-wiki-assistant/docker-compose.yml` real no declaró explícitamente redes compartidas, como `bdc-net`. Si en el futuro es necesario modificar `llm-wiki-assistant` para que el `include:` funcione en red, esto deberá solicitarse explícitamente y con confirmación, dado que es un entorno en producción).*

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
