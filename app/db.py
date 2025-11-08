"""
Database configuration and session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# SQLAlchemy setup
def get_database_url() -> str:
    """Get database URL from environment variables."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    
    # Construct from individual components
    user = os.getenv("SUPABASE_DB_USER", "postgres")
    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    host = os.getenv("SUPABASE_DB_HOST", "")
    port = os.getenv("SUPABASE_DB_PORT", "5432")
    dbname = os.getenv("SUPABASE_DB_NAME", "postgres")
    
    if not host:
        # Return a placeholder URL that will fail gracefully
        return "postgresql://postgres:password@localhost:5432/postgres"
    
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


DATABASE_URL = get_database_url()

# Create engine with lazy connection (connect_on_validate=False)
# This allows the app to start even if database is not available
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5} if DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Supabase Storage client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_supabase() -> Client:
    """Dependency for getting Supabase client."""
    if supabase is None:
        raise RuntimeError("Supabase client not initialized. Check environment variables.")
    return supabase

