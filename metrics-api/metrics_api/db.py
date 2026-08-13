import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://metrics_user:metrics_pass@postgres:5432/mapeo_db"
)

# Connect to the metrics schema
engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-csearch_path=metrics"}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
