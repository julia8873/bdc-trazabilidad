import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db"
)

connect_args = {}
if "postgresql" in DATABASE_URL:
    connect_args = {"options": "-csearch_path=metrics"}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
