import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
 
load_dotenv()
 
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "recruitment_copilot")
 
# URL-encode the password: special characters like @ : / would otherwise
# break the connection string's user:password@host parsing.
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
 
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
 
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
 
 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 
 
def init_db():
    """Create all tables. Call this once on startup."""
    from app.models import candidate, job, interview, voice_screening  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)