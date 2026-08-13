import pytest
import asyncio
import os
import json
import logging
from unittest.mock import patch, MagicMock
from metrics_worker.worker import SyncEventWorker, MissingCredentialsError

@pytest.fixture
def capture_logs(caplog):
    caplog.set_level(logging.INFO, logger="metrics_worker")
    return caplog

@pytest.mark.asyncio
async def test_idempotency(capture_logs):
    worker = SyncEventWorker(use_mock=True)
    worker.processed_hashes.add("hash1")
    
    events = [
        {"id": "ev1", "commit": "hash1", "msg": "msg1"},
        {"id": "ev2", "commit": "hash2", "msg": "msg2"}
    ]
    with patch.object(worker, 'get_events', return_value=events):
        stats = await worker.run_cycle()
        
        assert stats["total_encontrados"] == 2
        assert stats["skipped_idempotencia"] == 1
        assert stats["procesados"] == 1
        assert stats["fallidos"] == 0

@pytest.mark.asyncio
async def test_rate_limit_backoff():
    worker = SyncEventWorker(use_mock=True)
    
    events = [
        {"id": "ev1", "commit": "hash_fail", "force_fail": True}
    ]
    
    with patch.object(worker, 'get_events', return_value=events):
        with patch('metrics_worker.worker.logger.error') as mock_error:
            stats = await worker.run_cycle()
            
            assert stats["fallidos"] == 1
            # Confirmamos que se marco como fallido
            mock_error.assert_called_with("Evento marcado como fallido tras agotar reintentos", extra={'extra_info': {'event_hash': 'hash_fail', 'status': 'failed'}})

def test_fail_fast():
    with patch.dict(os.environ, {"MOCK_SERVICES": "false"}, clear=True):
        with pytest.raises(MissingCredentialsError, match="Fallo fail-fast: MOCK_SERVICES=false pero no se proporcionaron credenciales"):
            SyncEventWorker()
            
    with patch.dict(os.environ, {"MOCK_SERVICES": "false", "REPO_TOKEN": "secret"}, clear=True):
        # Esto no deberia lanzar excepcion
        SyncEventWorker()

@pytest.mark.asyncio
async def test_mock_mode():
    with patch.dict(os.environ, {"MOCK_SERVICES": "true"}, clear=True):
        worker = SyncEventWorker()
        events = await worker.get_events()
        assert len(events) == 2
        assert events[0]["id"] == "ev1"

@pytest.mark.asyncio
async def test_structured_logging(capture_logs):
    worker = SyncEventWorker(use_mock=True)
    
    events = [{"id": "ev1", "commit": "hash1", "msg": "msg1"}]
    with patch.object(worker, 'get_events', return_value=events):
        await worker.run_cycle()
        
    found_cycle = False
    for record in capture_logs.records:
        if record.message == "Ciclo de polling completado":
            found_cycle = True
            assert getattr(record, "extra_info", {})["total_encontrados"] == 1
            assert getattr(record, "extra_info", {})["procesados"] == 1
            assert getattr(record, "extra_info", {})["fallidos"] == 0
            assert "duracion_segundos" in getattr(record, "extra_info", {})
            
    assert found_cycle, "No se emitio el log estructurado del ciclo"

