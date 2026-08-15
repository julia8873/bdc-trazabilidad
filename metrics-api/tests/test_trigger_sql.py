import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError

def test_auditoria_append_only_trigger_update(db_session):
    db_session.execute(text("""
        INSERT INTO metrics.auditoria_accesos (id, moodle_username, recurso, resultado, metadatos) 
        VALUES ('00000000-0000-0000-0000-000000000001', 'testuser', '/token', 'SUCCESS', '{}')
    """))
    db_session.commit()

    with pytest.raises(InternalError) as exc_info:
        db_session.execute(text("""
            UPDATE metrics.auditoria_accesos SET resultado = 'MODIFIED' 
            WHERE id = '00000000-0000-0000-0000-000000000001'
        """))
    
    assert "append-only" in str(exc_info.value).lower() or "trigger" in str(exc_info.value).lower()

def test_auditoria_append_only_trigger_delete(db_session):
    db_session.execute(text("""
        INSERT INTO metrics.auditoria_accesos (id, moodle_username, recurso, resultado, metadatos) 
        VALUES ('00000000-0000-0000-0000-000000000002', 'testuser', '/token', 'SUCCESS', '{}')
    """))
    db_session.commit()

    with pytest.raises(InternalError) as exc_info:
        db_session.execute(text("""
            DELETE FROM metrics.auditoria_accesos 
            WHERE id = '00000000-0000-0000-0000-000000000002'
        """))
    
    assert "append-only" in str(exc_info.value).lower() or "trigger" in str(exc_info.value).lower()
