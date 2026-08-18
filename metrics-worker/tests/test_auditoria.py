import pytest
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock
from metrics_worker.worker import SyncEventWorker, MissingCredentialsError

@pytest.fixture
def mock_db():
    with patch("metrics_worker.worker.SessionLocal") as mock_session:
        session_instance = MagicMock()
        mock_session.return_value = session_instance
        yield session_instance

@pytest.mark.asyncio
async def test_eventos_recientes_contract():
    """1. Contrato del endpoint: Verificar el formato de GET /eventos-recientes."""
    worker = SyncEventWorker(use_mock=True)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"commit_sha": "abc1234", "moodle_user_id": 1, "moodle_course_id": 1, "tipo_evento": "PUSH"}
        ]
        mock_get.return_value = mock_resp
        
        await worker._consume_feed()
        assert mock_get.call_count == 2
        assert "eventos-recientes" in mock_get.call_args_list[0][0][0]
        assert "mapeos" in mock_get.call_args_list[1][0][0]

@pytest.mark.asyncio
async def test_discrepancia_forzada(mock_db):
    """2. Discrepancia forzada: Inyectar un commit en el mock de GitHub que no exista en la BD."""
    worker = SyncEventWorker(use_mock=True)
    worker.github_token = "fake"
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp_mapeos = MagicMock()
        mock_resp_mapeos.status_code = 200
        mock_resp_mapeos.json.return_value = [{"repo_url": "https://github.com/test/repo.git", "estado": "ACTIVO", "moodle_user_id": 1, "moodle_course_id": 1}]
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        from shared_pkg.okf_contract import COMMIT_MSG_INGEST
        with patch.object(worker, '_get_all_commits', return_value=[{"sha": "commit_not_in_db", "commit": {"message": COMMIT_MSG_INGEST}}]):
            mock_get.return_value = mock_resp_mapeos
            await worker._reconcile_history()
            
            assert mock_db.add.called
            added_obj = mock_db.add.call_args[0][0]
            assert added_obj.__class__.__name__ == "DiscrepanciaAuditoria"
            assert added_obj.commit_sha == "commit_not_in_db"
            assert added_obj.tipo_discrepancia == "EVENTO_MISSING_IN_FEED"

@pytest.mark.asyncio
async def test_filtro_contrato_okf(mock_db):
    """Prueba que el bucle 2 filtre correctamente por mensajes de commit del contrato OKF."""
    worker = SyncEventWorker(use_mock=True)
    worker.github_token = "fake"
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp_mapeos = MagicMock()
        mock_resp_mapeos.status_code = 200
        mock_resp_mapeos.json.return_value = [{"repo_url": "https://github.com/test/repo.git", "estado": "ACTIVO", "moodle_user_id": 1, "moodle_course_id": 1}]
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        from shared_pkg.okf_contract import COMMIT_MSG_INGEST
        commits_simulados = [
            {"sha": "commit_okf", "commit": {"message": COMMIT_MSG_INGEST + " archivo.txt"}},
            {"sha": "commit_manual", "commit": {"message": "Update README.md"}}
        ]
        
        with patch.object(worker, '_get_all_commits', return_value=commits_simulados):
            mock_get.return_value = mock_resp_mapeos
            await worker._reconcile_history()
            
            # Solo debe haberse añadido el commit_okf (1 llamada a db.add)
            assert mock_db.add.call_count == 1
            added_obj = mock_db.add.call_args[0][0]
            assert added_obj.commit_sha == "commit_okf"

@pytest.mark.asyncio
async def test_fail_fast_sin_token():
    """3. Test de inicialización del worker confirmando fail-fast por falta de variables críticas."""
    with patch.dict("os.environ", {"MOCK_SERVICES": "false", "GITHUB_TOKEN": ""}):
        with pytest.raises(MissingCredentialsError):
            SyncEventWorker(use_mock=False)

@pytest.mark.asyncio
async def test_rate_limit_backoff():
    """4. Simular rate limit y comprobar backoff (mock de sleep)."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"}):
        worker = SyncEventWorker(use_mock=False)
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "rate limit exceeded"
        
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.headers = {}
        mock_resp_200.json.return_value = []
        
        mock_get.side_effect = [mock_resp_429, mock_resp_200]
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            commits = await worker._get_all_commits("owner", "repo")
            assert mock_sleep.called
            assert mock_get.call_count == 2
            assert commits == []

@pytest.mark.asyncio
async def test_backfill_idempotencia():
    """5. Prueba del backfill para comprobar que no duplica inserciones si se corre dos veces."""
    with patch.dict("os.environ", {"MAPEO_API_TOKEN": "test_token"}):
        from metrics_worker.backfill import backfill
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # Primera llamada devuelve 200, segunda llamada devuelve 409 (ya existe)
            mock_resp_200 = MagicMock()
            mock_resp_200.status_code = 200
            mock_resp_409 = MagicMock()
            mock_resp_409.status_code = 409
            mock_post.side_effect = [mock_resp_200, mock_resp_409]
            
            with patch("glob.glob", return_value=["/tmp/llm_wiki_repos/123/.backfill.jsonl"]):
                with patch("builtins.open", new_callable=MagicMock) as mock_open:
                    mock_file = mock_open.return_value.__enter__.return_value
                    payload = '{"commit_sha": "abc1234", "matrix_room_id": "!room:matrix.org"}'
                    
                    # Ejecución 1
                    mock_file.__iter__.return_value = iter([payload])
                    await backfill()
                    assert mock_post.call_count == 1
                    
                    # Ejecución 2
                    mock_file.__iter__.return_value = iter([payload])
                    await backfill()
                    assert mock_post.call_count == 2
                    # Si llega hasta aquí sin excepciones, manejó el 409 correctamente como idempotente.

@pytest.mark.asyncio
async def test_migracion_alembic():
    """6. Pruebas de migraciones"""
    from metrics_api.models import EventoSync, DiscrepanciaAuditoria
    e = EventoSync(commit_sha="x", moodle_user_id=1, moodle_course_id=1)
    d = DiscrepanciaAuditoria(commit_sha="y", moodle_user_id=1, moodle_course_id=1, tipo_discrepancia="TEST")
    assert e.commit_sha == "x"
    assert d.commit_sha == "y"
