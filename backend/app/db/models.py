"""
DATABASE ORM MODELS
===================
These are SQLAlchemy models — Python classes that map directly to database tables.

HOW ORM WORKS:
  Python Class  ←→  Database Table
  Class Field   ←→  Table Column
  Class Instance ←→ Table Row

Example:
  # This Python code:
  record = UploadRecord(filename="sales.csv", row_count=500)
  db.add(record)
  db.commit()
  
  # Becomes this SQL automatically:
  INSERT INTO upload_records (filename, row_count, ...) VALUES ('sales.csv', 500, ...)

WHY NOT RAW SQL?
  1. Type safety — Python catches errors before they hit the database
  2. Portability — same code works with SQLite, PostgreSQL, MySQL
  3. Relationships — ORM handles JOINs through Python objects
  4. Migrations — tools like Alembic can auto-detect schema changes
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.models.database import Base


class UploadRecord(Base):
    """
    Tracks every CSV file uploaded to InsightFlow.
    
    Each upload creates one row in this table. This lets users
    see their upload history and re-visit past analyses.
    
    Table name: 'upload_records' (SQLAlchemy auto-generates from class name,
    but we explicitly set it for clarity)
    """
    __tablename__ = "upload_records"

    # Primary key — auto-incrementing integer
    # Every table needs a unique identifier for each row
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # File metadata
    filename = Column(String(255), nullable=False)          # Original filename
    file_size_bytes = Column(Integer, nullable=False)       # File size for display

    # Dataset stats (stored so we don't need to re-analyze)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    
    # Analysis results
    insights_count = Column(Integer, default=0)             # How many insights were generated
    critical_count = Column(Integer, default=0)             # Critical severity count
    warning_count = Column(Integer, default=0)              # Warning severity count
    
    # Summary text
    summary = Column(Text, nullable=True)                   # Plain-English summary

    # Timestamps
    # func.now() tells SQLAlchemy to use the database's current timestamp
    # server_default means the DEFAULT is set in the SQL schema itself
    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self):
        """String representation for debugging"""
        return f"<Upload #{self.id}: {self.filename} ({self.row_count} rows)>"


class QueryRecord(Base):
    """
    Tracks every natural-language query made through the pipeline.
    
    This lets users:
    1. See their question history
    2. Re-visit past answers without re-running the pipeline
    3. Build a conversation thread about a dataset
    
    Table name: 'query_records'
    """
    __tablename__ = "query_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Link to the dataset
    filename = Column(String(255), nullable=False)
    
    # Query info
    query = Column(Text, nullable=False)           # Original user question
    intent = Column(String(50), nullable=True)     # Classified intent
    confidence = Column(String(20), nullable=True) # High, Medium, Low
    
    # Response
    explanation = Column(Text, nullable=True)       # Generated explanation
    
    # Pipeline metadata (stored as JSON string)
    pipeline_log_json = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self):
        return f"<Query #{self.id}: '{self.query[:50]}...' ({self.intent})>"
