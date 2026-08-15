import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from metrics_api.main import app
from metrics_api.db import get_session
from metrics_api.models import Base

# Usamos PostgreSQL para tests de integración
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db"
)

# Connect to the metrics schema
engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-csearch_path=metrics"}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def engine_fixture():
    # En producción / docker-compose de desarrollo el esquema 'metrics'
    # y las tablas ya existen por Alembic.
    return engine

@pytest.fixture()
def db_session(engine_fixture):
    connection = engine_fixture.connect()
    # Iniciar transacción que nunca se comitea
    transaction = connection.begin()
    
    session = TestingSessionLocal(bind=connection)
    
    # Nested transaction para poder hacer rollbacks dentro de los tests sin romper la outer
    session.begin_nested()
    
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()
            
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture()
def client(db_session):
    def override_get_session():
        yield db_session
    
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    del app.dependency_overrides[get_session]
