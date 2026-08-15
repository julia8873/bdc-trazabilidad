import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import asyncio

def test_auditoria_incremental_since():
    """Test del Auditor Incremental para verificar el parametro since."""
    from metrics_worker.worker import SyncEventWorker
    from metrics_api.models import AuditoriaEstado
    
    worker = SyncEventWorker(use_mock=True)
    worker.github_token = "fake"
    
    with patch("metrics_worker.worker.SessionLocal") as mock_session:
        session_instance = MagicMock()
        mock_session.return_value = session_instance
        
        # Mapeos simulados
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp_mapeos = MagicMock()
            mock_resp_mapeos.status_code = 200
            mock_resp_mapeos.json.return_value = [{
                "repo_url": "https://github.com/owner/repo.git", 
                "moodle_user_id": 1, 
                "moodle_course_id": 1,
                "estado": "ACTIVO"
            }]
            mock_get.return_value = mock_resp_mapeos
            
            # Estado simulado
            estado = AuditoriaEstado(
                moodle_user_id=1, moodle_course_id=1, 
                repo_owner="owner", repo_name="repo", 
                last_audited_timestamp=datetime(2026, 1, 1, 12, 0, 0)
            )
            session_instance.query.return_value.filter.return_value.first.return_value = estado
            
            with patch.object(worker, '_get_all_commits', new_callable=AsyncMock) as mock_get_commits:
                mock_get_commits.return_value = []
                
                asyncio.run(worker._reconcile_history())
                
                # Check that _get_all_commits was called with the correct since parameter
                mock_get_commits.assert_called_once_with("owner", "repo", since="2026-01-01T12:00:00Z")
