"""
DATABASE CONNECTION SETUP
=========================
This file creates the SQLAlchemy "engine" (the connection to our database)
and a "session factory" (creates sessions for each request).

KEY CONCEPTS:
- Engine: Think of it as the database connection pool. It manages
  connections to SQLite (or PostgreSQL later).
  
- SessionLocal: A factory that creates new database sessions.
  Each API request gets its own session to avoid conflicts.
  
- Base: All our ORM models inherit from this. When we call
  Base.metadata.create_all(), it creates all the tables.

- get_db(): A "dependency injection" function. FastAPI calls this
  automatically for any route that needs database access.
  The `yield` keyword makes it a generator — the session is created
  before the route runs and closed after it finishes (even if there's an error).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Database file location — stored in the backend directory
# SQLite uses a file path, not a network address like PostgreSQL
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'insightflow.db')}"

# Create the engine
# connect_args={"check_same_thread": False} is SQLite-specific.
# SQLite by default only allows the thread that created it to use it.
# FastAPI is async and may use different threads, so we disable this check.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True to see SQL queries in console (useful for debugging)
)

# Session factory — each call to SessionLocal() creates a new session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """
    Dependency injection for FastAPI routes.
    
    Usage in a route:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    
    The `yield` makes this a context manager:
    1. Creates a session BEFORE the route handler runs
    2. The route uses the session
    3. Session is closed AFTER the route finishes (in the finally block)
    
    This pattern ensures we never leak database connections.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
