import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
 
load_dotenv()
 
# Full connection string override (this is what Render/Railway/etc. inject
# automatically when you attach a managed Postgres database). If it's not
# set, we fall back to building a MySQL URL from the individual DB_* vars
# below (for local dev), and if THOSE aren't set either, we fall back to a
# local SQLite file so the app can run with zero external database setup --
# handy for a free/simple deployment.
DATABASE_URL = os.getenv("DATABASE_URL")
 
if not DATABASE_URL:
    DB_HOST = os.getenv("DB_HOST")
    if DB_HOST:
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
    else:
        DATABASE_URL = "sqlite:///./recruitment_copilot.db"
 
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
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
    from app.models import candidate, job, interview, voice_screening, voice_interview  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
