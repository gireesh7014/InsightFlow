"""
FASTAPI MAIN APPLICATION
========================
This is the entry point of your backend. It creates the FastAPI app,
configures middleware, and defines all API routes.

HOW FASTAPI WORKS:
  1. You define functions decorated with @app.get(), @app.post(), etc.
  2. FastAPI maps URLs to these functions
  3. When a request comes in, FastAPI:
     a) Validates the input using Pydantic models
     b) Calls your function with the validated data
     c) Serializes your return value to JSON
     d) Sends the response
  4. Auto-generates Swagger docs at /docs

KEY CONCEPTS:
  - Routes: URL → function mapping (like @app.post("/analyze"))
  - Dependencies: Functions that run before your route (like get_db())
  - Middleware: Code that runs for EVERY request (like CORS)
  - UploadFile: FastAPI's file upload handler
"""

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pandas as pd
import io
import logging
import time

from app.models.database import engine, get_db, Base
from app.models.schemas import AnalysisResponse, UploadHistoryItem, ErrorResponse
from app.db.models import UploadRecord
from app.services.analyzer import analyze_dataframe, generate_summary
from app.services.rule_engine import run_rule_engine
from app.services.visualizer import generate_all_charts

# ─── Logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("insightflow")

# ─── Create FastAPI app ───────────────────────────────────────
app = FastAPI(
    title="InsightFlow API",
    description="Decision Intelligence System — Upload CSV data and get ranked, explainable insights",
    version="1.0.0",
    docs_url="/docs",      # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",     # ReDoc at http://localhost:8000/redoc
)

# ─── CORS Middleware ──────────────────────────────────────────
"""
WHAT IS CORS?
  Cross-Origin Resource Sharing. When your frontend (localhost:3000) 
  makes a request to your backend (localhost:8000), the browser blocks 
  it by default because they're on different "origins" (different ports).
  
  CORS headers tell the browser: "It's okay, I trust this origin."
  
  allow_origins: Which frontend URLs can access this API
  allow_methods: Which HTTP methods are allowed (GET, POST, etc.)
  allow_headers: Which HTTP headers the frontend can send
  
  In production, you'd restrict origins to your actual domain.
  For development, we allow all origins with "*".
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],         # Allow all HTTP methods
    allow_headers=["*"],         # Allow all headers
)

# ─── Create database tables on startup ────────────────────────
"""
This runs once when the server starts. It creates all tables defined
by our SQLAlchemy models (if they don't already exist).

In production, you'd use Alembic for migrations instead.
"""
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")


# ═══════════════════════════════════════════════════════════════
# ROUTE: POST /analyze — Main analysis endpoint
# ═══════════════════════════════════════════════════════════════
@app.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Analyze a CSV file",
    description="Upload a CSV file and receive comprehensive statistical analysis, "
                "ranked insights, correlation analysis, and auto-generated charts."
)
async def analyze_csv(
    file: UploadFile = File(..., description="CSV file to analyze"),
    db: Session = Depends(get_db)
):
    """
    Main analysis endpoint. This is where the magic happens:
    
    1. Validate the uploaded file (must be CSV)
    2. Parse it into a pandas DataFrame
    3. Run the analysis engine (statistics for every column)
    4. Run the rule engine (20 insight rules)
    5. Generate charts (heatmaps, distributions, etc.)
    6. Generate a plain-English summary
    7. Save the upload record to the database
    8. Return everything in a structured JSON response
    
    HOW FILE UPLOAD WORKS IN FASTAPI:
      - The frontend sends the file as multipart/form-data
      - FastAPI receives it as an UploadFile object
      - UploadFile.read() gives us the raw bytes
      - We wrap those bytes in a BytesIO to create a file-like object
      - pandas.read_csv() can read from any file-like object
    """
    start_time = time.time()
    
    # ─── Step 1: Validate file type ─────────────────────────
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid file type",
                "detail": f"Expected a CSV file, got '{file.filename}'",
                "suggestion": "Please upload a file with .csv extension"
            }
        )
    
    # ─── Step 2: Read and parse the CSV ─────────────────────
    try:
        contents = await file.read()
        file_size = len(contents)
        
        # Limit file size to 50MB
        if file_size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File too large",
                    "detail": f"File size: {file_size / (1024*1024):.1f}MB. Maximum: 50MB",
                    "suggestion": "Try sampling your dataset or removing unnecessary columns"
                }
            )
        
        # Parse CSV — BytesIO makes bytes look like a file to pandas
        df = pd.read_csv(io.BytesIO(contents))
        logger.info(f"Parsed '{file.filename}': {len(df)} rows × {len(df.columns)} columns")
        
    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Empty file",
                "detail": "The uploaded CSV file is empty",
                "suggestion": "Please upload a CSV file with data"
            }
        )
    except pd.errors.ParserError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "CSV parsing error",
                "detail": f"Could not parse the file: {str(e)}",
                "suggestion": "Check that the file is a valid CSV with consistent delimiters"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "File reading error",
                "detail": str(e),
                "suggestion": "Ensure the file is a valid, readable CSV"
            }
        )
    
    # ─── Step 3: Validate data ──────────────────────────────
    if len(df) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No data rows",
                "detail": "The CSV file has headers but no data rows",
                "suggestion": "Upload a CSV with at least a few rows of data"
            }
        )
    
    if len(df.columns) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No columns",
                "detail": "Could not detect any columns in the CSV",
                "suggestion": "Check that the CSV has a header row"
            }
        )
    
    # ─── Step 4: Run the analysis engine ────────────────────
    logger.info("Running analysis engine...")
    analysis = analyze_dataframe(df, file.filename, file_size)
    
    # ─── Step 5: Run the rule engine ────────────────────────
    logger.info("Running rule engine (20 rules)...")
    insights = run_rule_engine(
        df=df,
        columns_stats=analysis["columns"],
        numeric_cols=analysis["numeric_columns"],
        categorical_cols=analysis["categorical_columns"],
        datetime_cols=analysis["datetime_columns"],
        notable_correlations=analysis["notable_correlations"]
    )
    
    # Count insights by severity
    insight_summary = {"critical": 0, "warning": 0, "info": 0}
    for insight in insights:
        insight_summary[insight.severity] = insight_summary.get(insight.severity, 0) + 1
    
    logger.info(f"Generated {len(insights)} insights: {insight_summary}")
    
    # ─── Step 6: Generate charts ────────────────────────────
    logger.info("Generating charts...")
    charts = generate_all_charts(df, analysis["numeric_columns"])
    
    # ─── Step 7: Generate plain-English summary ─────────────
    summary = generate_summary(
        filename=file.filename,
        row_count=analysis["row_count"],
        column_count=analysis["column_count"],
        numeric_cols=analysis["numeric_columns"],
        categorical_cols=analysis["categorical_columns"],
        datetime_cols=analysis["datetime_columns"],
        insights_summary=insight_summary,
        notable_correlations=analysis["notable_correlations"]
    )
    
    # ─── Step 8: Save to database ───────────────────────────
    try:
        upload_record = UploadRecord(
            filename=file.filename,
            file_size_bytes=file_size,
            row_count=analysis["row_count"],
            column_count=analysis["column_count"],
            insights_count=len(insights),
            critical_count=insight_summary.get("critical", 0),
            warning_count=insight_summary.get("warning", 0),
            summary=summary
        )
        db.add(upload_record)
        db.commit()
        logger.info(f"Saved upload record #{upload_record.id}")
    except Exception as e:
        logger.error(f"Failed to save upload record: {e}")
        db.rollback()
        # Don't fail the whole request — the analysis is still valid
    
    # ─── Step 9: Build response ─────────────────────────────
    elapsed = time.time() - start_time
    logger.info(f"Analysis complete in {elapsed:.2f}s")
    
    return AnalysisResponse(
        filename=analysis["filename"],
        file_size_bytes=analysis["file_size_bytes"],
        row_count=analysis["row_count"],
        column_count=analysis["column_count"],
        memory_usage_mb=analysis["memory_usage_mb"],
        columns=analysis["columns"],
        numeric_columns=analysis["numeric_columns"],
        categorical_columns=analysis["categorical_columns"],
        datetime_columns=analysis["datetime_columns"],
        insights=insights,
        insight_summary=insight_summary,
        correlation_matrix=analysis["correlation_matrix"],
        notable_correlations=analysis["notable_correlations"],
        charts=charts,
        distributions=analysis["distributions"],
        summary=summary
    )


# ═══════════════════════════════════════════════════════════════
# ROUTE: GET /history — Upload history
# ═══════════════════════════════════════════════════════════════
@app.get(
    "/history",
    response_model=list[UploadHistoryItem],
    summary="Get upload history",
    description="Returns the most recent 20 uploads with their metadata"
)
def get_history(db: Session = Depends(get_db)):
    """
    Returns past uploads so the user can see their analysis history.
    Sorted by most recent first, limited to 20 entries.
    """
    records = (
        db.query(UploadRecord)
        .order_by(UploadRecord.uploaded_at.desc())
        .limit(20)
        .all()
    )
    return records


# ═══════════════════════════════════════════════════════════════
# ROUTE: GET /health — Health check
# ═══════════════════════════════════════════════════════════════
@app.get("/health", summary="Health check")
def health_check():
    """
    Simple health check endpoint. Returns 200 if the server is running.
    Used by deployment platforms (Railway, Render) to verify the server is alive.
    """
    return {"status": "healthy", "service": "InsightFlow API", "version": "1.0.0"}
