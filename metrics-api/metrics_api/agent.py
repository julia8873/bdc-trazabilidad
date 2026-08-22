import os
import httpx
import yaml
import hmac
import hashlib
import time
import json
from datetime import datetime, timezone
from fastapi import HTTPException, status
from typing import Dict, Any, Tuple, List
from pydantic import BaseModel

from metrics_api.schemas import (
    AgentSummaryResponse, 
    AgentFollowUpResponse, 
    AgentFollowUpRequest,
    AgentFollowUpMessage, 
    CriterioEvaluacion
)

# Cache in-memory
# format: { "curso_id_alumno_id": {"summary": dict, "timestamp": float} }
_SUMMARY_CACHE = {}

AGENT_HMAC_SECRET = os.getenv("AGENT_HMAC_SECRET", "default_agent_hmac_secret_for_testing")

def load_rubric() -> Dict:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "rubrica_evaluacion.yaml")
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        return {"version_rubrica": "error", "criterios": [], "instrucciones_agente": ""}

def load_shared_config() -> Dict:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "config.yaml")
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

def load_llm_config() -> Dict:
    # Read from llm-wiki-assistant config
    path = "/home/julia/llm-wiki-assistant/config/config.yaml"
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f).get("llm", {})
    except Exception:
        return {}

def generate_summary_hash(curso_id: int, alumno_id: int, summary_dict: dict) -> str:
    """Generate a secure HMAC hash of the summary to prevent tampering during follow-ups."""
    content = f"{curso_id}_{alumno_id}_{json.dumps(summary_dict, sort_keys=True)}"
    return hmac.new(AGENT_HMAC_SECRET.encode(), content.encode(), hashlib.sha256).hexdigest()

async def get_mapeo(curso_id: int, alumno_id: int) -> dict:
    mapeo_api_url = os.getenv("MAPEO_API_URL", "http://localhost:8001")
    mapeo_api_token = os.getenv("MAPEO_API_TOKEN")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{mapeo_api_url}/v1/mapeos",
                params={"moodle_course_id": curso_id, "moodle_user_id": alumno_id},
                headers={"Authorization": f"Bearer {mapeo_api_token}"}
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                if not data:
                    raise HTTPException(status_code=404, detail="Mapeo no encontrado")
                return data[0]
            else:
                if not data.get("data"):
                    raise HTTPException(status_code=404, detail="Mapeo no encontrado")
                return data["data"][0]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Mapeo no encontrado")
            raise HTTPException(status_code=500, detail=f"Error consultando mapeo: {str(e)}")

async def get_github_diffs(repo_url: str) -> str:
    github_token = os.getenv("GITHUB_TOKEN_AGENT")
    if not github_token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN_AGENT no configurado")
    
    # repo_url format: https://github.com/org/repo
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        return ""
    owner, repo = parts[-2], parts[-1]
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    diff_content = ""
    async with httpx.AsyncClient() as client:
        try:
            # Get latest commits
            commits_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"per_page": 10}
            )
            if commits_resp.status_code == 404:
                # Mock diff for demo purposes
                return "diff --git a/ejercicio.py b/ejercicio.py\n+ def suma(a, b):\n+    return a + b\n"
            commits_resp.raise_for_status()
            commits = commits_resp.json()
            
            if not commits:
                return ""
                
            for c in commits[:5]:
                sha = c["sha"]
                commit_msg = c["commit"]["message"]
                if "Merge" in commit_msg or "Initial commit" in commit_msg:
                    continue
                # Get diff
                diff_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}",
                    headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3.diff"}
                )
                if diff_resp.status_code == 200:
                    diff_content += f"\n--- Commit: {commit_msg} ---\n"
                    diff_content += diff_resp.text[:2000] # truncate per commit
                    
        except httpx.HTTPError:
            pass # Return what we have or empty
            
    return diff_content

async def invoke_llm(system_prompt: str, user_content: str, response_format=None) -> Any:
    llm_cfg = load_llm_config()
    provider = llm_cfg.get("proveedor_activo", "gemini")
    
    if provider == "gemini":
        gemini_cfg = llm_cfg.get("gemini", {})
        api_key = os.getenv(gemini_cfg.get("api_key_env_var", "GEMINI_API_KEY"), gemini_cfg.get("api_key"))
        model = gemini_cfg.get("modelo_defecto", "gemini-2.5-flash") # Use 2.5 that supports JSON
        base_url = gemini_cfg.get("api_base_url", "https://generativelanguage.googleapis.com/v1beta")
        
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [{
                "parts": [{"text": user_content}]
            }],
            "generationConfig": {
                "temperature": 0.2,
            }
        }
        
        if response_format == "json":
            payload["generationConfig"]["response_mime_type"] = "application/json"
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                if response_format == "json":
                    # Remove markdown blocks if present
                    text = text.replace("```json", "").replace("```", "").strip()
                    return json.loads(text)
                return text
            except Exception as e:
                raise HTTPException(status_code=500, detail="Error parseando respuesta LLM")
    else:
        # Fallback or other providers not fully implemented for this phase snippet
        raise HTTPException(status_code=500, detail=f"LLM Provider {provider} not supported for JSON format yet")

async def generar_resumen(curso_id: int, alumno_id: int) -> AgentSummaryResponse:
    if os.getenv("ENABLE_EVALUATION_AGENT", "false").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Agent evaluation is currently disabled."
        )
        
    shared_config = load_shared_config()
    timings = shared_config.get("timings", {})
    ttl_min = timings.get("agent_summary_cache_ttl_min", 60)
    retention_days = timings.get("fork_retention_days_after_course_close", 30)
    
    cache_key = f"{curso_id}_{alumno_id}"
    now = time.time()
    if cache_key in _SUMMARY_CACHE:
        cached = _SUMMARY_CACHE[cache_key]
        if now - cached["timestamp"] < ttl_min * 60:
            return AgentSummaryResponse(**cached["summary"])
            
    # Check mapeo
    mapeo = await get_mapeo(curso_id, alumno_id)
    
    # Check retention
    close_date_str = mapeo.get("course_close_date")
    created_at_str = mapeo.get("created_at")
    
    # Secure default: If course close date is unknown, apply a fallback limit from the creation date
    fallback_retention_days = timings.get("fallback_retention_days_if_no_close_date", 180)
    
    date_to_check_str = close_date_str if close_date_str else created_at_str
    days_to_check = retention_days if close_date_str else fallback_retention_days
    
    if date_to_check_str:
        # Assuming ISO format
        try:
            if date_to_check_str.endswith('Z'):
                date_to_check_str = date_to_check_str[:-1] + '+00:00'
            ref_date = datetime.fromisoformat(date_to_check_str)
            if ref_date.tzinfo is None:
                ref_date = ref_date.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - ref_date
            
            if delta.days > days_to_check:
                motivo = "El curso está cerrado y" if close_date_str else "El repositorio no tiene fecha de cierre registrada pero superó el límite máximo de seguridad y está"
                raise HTTPException(
                    status_code=410,
                    detail=f"{motivo} fuera del periodo de retención de forks."
                )
        except ValueError:
            pass
            
    repo_url = mapeo.get("repo_url")
    if not repo_url:
        return AgentSummaryResponse(estado="sin_actividad")
        
    diffs = await get_github_diffs(repo_url)
    if not diffs.strip():
        return AgentSummaryResponse(estado="sin_actividad")
        
    rubrica = load_rubric()
    version = rubrica.get("version_rubrica", "1.0")
    instrucciones = rubrica.get("instrucciones_agente", "")
    
    system_prompt = f"""
{instrucciones}

Rúbrica de Criterios:
{json.dumps(rubrica.get('criterios', []), ensure_ascii=False, indent=2)}

Devuelve estrictamente un JSON con esta estructura exacta (no añadas nada más, no uses notas numéricas):
{{
  "criterios": [{{"nombre": "nombre_criterio", "observacion": "texto"}}],
  "fortalezas": ["texto"],
  "patrones_uso": ["texto"],
  "senales_alerta": ["texto"]
}}
"""
    
    user_content = f"--- INICIO DEL CONTENIDO DEL ESTUDIANTE ---\n{diffs}\n--- FIN DEL CONTENIDO DEL ESTUDIANTE ---"
    
    # LLM Call
    llm_result = await invoke_llm(system_prompt, user_content, response_format="json")
    
    summary_dict = {
        "estado": "evaluado",
        "criterios": llm_result.get("criterios", []),
        "fortalezas": llm_result.get("fortalezas", []),
        "patrones_uso": llm_result.get("patrones_uso", []),
        "senales_alerta": llm_result.get("senales_alerta", []),
        "version_rubrica": version,
        "resumen_hash": ""
    }
    
    summary_dict["resumen_hash"] = generate_summary_hash(curso_id, alumno_id, summary_dict)
    
    _SUMMARY_CACHE[cache_key] = {
        "summary": summary_dict,
        "timestamp": now
    }
    
    return AgentSummaryResponse(**summary_dict)

async def seguimiento_resumen(curso_id: int, alumno_id: int, req: AgentFollowUpRequest) -> AgentFollowUpResponse:
    if os.getenv("ENABLE_EVALUATION_AGENT", "false").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Agent evaluation is currently disabled."
        )
        
    # Validar historial máximo
    if len(req.historial) > 6: # 3 turnos max (user, assistant, user, assistant, user, assistant)
        raise HTTPException(status_code=400, detail="Límite de turnos de seguimiento excedido.")
        
    cache_key = f"{curso_id}_{alumno_id}"
    if cache_key not in _SUMMARY_CACHE:
        raise HTTPException(status_code=400, detail="No existe un resumen activo para seguir la conversación.")
        
    cached = _SUMMARY_CACHE[cache_key]["summary"]
    # Verify hash
    expected_hash = cached.get("resumen_hash")
    if not expected_hash or not hmac.compare_digest(expected_hash, req.resumen_hash):
        raise HTTPException(status_code=400, detail="El hash del resumen no coincide o la conversación ha sido manipulada.")
        
    system_prompt = """Eres el mismo asistente que evaluó al estudiante. 
Responde de forma concisa y directa a la pregunta del profesor sobre la evaluación.
No inventes datos que no estuvieran en tu evaluación original."""

    # Build context
    historial_text = ""
    for msg in req.historial:
        historial_text += f"{msg.rol.upper()}: {msg.contenido}\n"
        
    user_content = f"Evaluación original:\n{json.dumps(cached, indent=2)}\n\nHistorial:\n{historial_text}\nPROFESOR: {req.mensaje}"
    
    # LLM Call
    llm_result_text = await invoke_llm(system_prompt, user_content, response_format="text")
    
    new_history = req.historial + [
        AgentFollowUpMessage(rol="user", contenido=req.mensaje),
        AgentFollowUpMessage(rol="assistant", contenido=llm_result_text)
    ]
    
    return AgentFollowUpResponse(
        respuesta=llm_result_text,
        historial_actualizado=new_history
    )
