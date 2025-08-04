"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from synthetic_data_service.config import db_config

# Create the SQLAlchemy base class for declarative models
Base = declarative_base()

# Create the engine based on the configuration
engine = create_engine(
    db_config.connection_string, 
    echo=False,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Session:
    """
    Get a database session.
    
    Returns:
        Session: A SQLAlchemy session object.
    """
    return SessionLocal()


def init_db(drop_all: bool = False):
    """
    Initialize the database by creating all tables.
    
    Args:
        drop_all (bool): If True, drop all existing tables before creating new ones.
    """
    if drop_all:
        Base.metadata.drop_all(bind=engine)
    
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all tables in the database."""
    Base.metadata.drop_all(bind=engine)