"""
test_no_hardcoded_timings.py — Fase 9

Verifica que NO existen valores de tiempo hardcodeados en el código de producción
de ambos repositorios (bdc-trazabilidad y la parte de mapeo-api en llm-wiki-assistant).

El escaneo se limita EXCLUSIVAMENTE a directorios de código de producción:
  - bdc-trazabilidad: metrics_api/, metrics_worker/, app/ (si existiera)
  - llm-wiki-assistant/moodle-matrix-dev/mapeo-api/app/

Los tests/ y scripts/ quedan EXCLUIDOS explícitamente para evitar falsos positivos
(timedelta en fixtures de tests de backoff, sleeps en scripts de backfill, etc.).
"""
import re
import os
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Directorios de código de producción a escanear
# ---------------------------------------------------------------------------
REPO_ROOT_BDC = pathlib.Path(__file__).parent.parent  # metrics-worker/tests/ -> metrics-worker/ -> bdc-trazabilidad/
BDC_ROOT = REPO_ROOT_BDC.parent  # bdc-trazabilidad/

if (pathlib.Path("/app/metrics_api")).exists() or (pathlib.Path("/app/metrics_worker")).exists():
    # Si estamos dentro del contenedor docker (donde se monta el código en /app o similar)
    # y los tests se corren directamente sobre /app.
    app_dir = pathlib.Path("/app")
    PRODUCTION_DIRS = [d for d in [app_dir / "metrics_api", app_dir / "metrics_worker"] if d.exists()]
else:
    PRODUCTION_DIRS = [
        BDC_ROOT / "metrics-api" / "metrics_api",
        BDC_ROOT / "metrics-worker" / "metrics_worker",
    ]

# mapeo-api está en llm-wiki-assistant: subir desde bdc-trazabilidad
MAPEO_API_DIR = BDC_ROOT.parent / "llm-wiki-assistant" / "moodle-matrix-dev" / "mapeo-api" / "app"
if MAPEO_API_DIR.exists():
    PRODUCTION_DIRS.append(MAPEO_API_DIR)

# ---------------------------------------------------------------------------
# Patrones prohibidos: valores numéricos hardcodeados en expresiones de tiempo
# ---------------------------------------------------------------------------
HARDCODED_TIMING_PATTERNS = [
    # timedelta con valor numérico literal (no variable)
    (r"timedelta\s*\(\s*(minutes|hours|days|seconds|weeks)\s*=\s*\d+", "timedelta con valor literal"),
    # time.sleep con literal (asyncio.sleep también)
    (r"\btime\.sleep\s*\(\s*\d+", "time.sleep con valor literal"),
    (r"\basynccio\.sleep\s*\(\s*\d+", "asyncio.sleep con valor literal"),
]

# Líneas/expresiones permitidas (whitelist): comentarios, strings de docs, etc.
WHITELIST_PATTERNS = [
    r"^\s*#",       # línea de comentario
    r"^\s*\"\"\"",  # docstring
    r"^\s*'''",     # docstring alternativo
]

def collect_python_files(dirs):
    files = []
    for d in dirs:
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            # Excluir tests dentro de directorios de producción (por si acaso)
            if "test" in f.name.lower():
                continue
            files.append(f)
    return files


def find_violations(files):
    violations = []
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            # Skip whitelisted lines
            if any(re.match(wp, line) for wp in WHITELIST_PATTERNS):
                continue
            for pattern, description in HARDCODED_TIMING_PATTERNS:
                if re.search(pattern, line):
                    violations.append({
                        "file": str(filepath),
                        "line": lineno,
                        "content": line.strip(),
                        "rule": description,
                    })
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_hardcoded_timedelta_in_production_code():
    """Verifica que no hay timedelta(minutes=X) ni timedelta(days=X) literales en producción."""
    files = collect_python_files(PRODUCTION_DIRS)
    assert files, f"No se encontraron ficheros Python en los directorios de producción: {PRODUCTION_DIRS}"

    violations = find_violations(files)
    if violations:
        report = "\n".join(
            f"  {v['file']}:{v['line']} [{v['rule']}]\n    {v['content']}"
            for v in violations
        )
        pytest.fail(
            f"Se encontraron {len(violations)} valor(es) de tiempo hardcodeado(s) en código de producción:\n{report}\n\n"
            "Mueve estos valores a config/config.yaml (bloque `timings`) y léelos desde allí."
        )


def test_production_dirs_exist():
    """Comprueba que los directorios de producción configurados existen."""
    missing = [str(d) for d in PRODUCTION_DIRS if not d.exists()]
    if missing:
        pytest.fail(f"Directorios de producción no encontrados: {missing}")


def test_config_yaml_has_timings_block():
    """Comprueba que bdc-trazabilidad/config/config.yaml tiene el bloque timings."""
    config_path = BDC_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        pytest.skip(f"No se encontró {config_path} (probablemente corriendo dentro del contenedor docker)")

    import yaml
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    assert data is not None, "config/config.yaml está vacío"
    assert "timings" in data, "Falta el bloque 'timings' en config/config.yaml"

    timings = data["timings"]
    required_keys = [
        "poll_interval_sec",
        "reconciliation_interval_sec",
        "access_token_expire_minutes",
        "refresh_token_expire_days",
    ]
    missing_keys = [k for k in required_keys if k not in timings]
    assert not missing_keys, f"Faltan claves en timings: {missing_keys}"
