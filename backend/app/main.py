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

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
import io
import json
import logging
import time

from app.models.database import engine, get_db, Base
from app.models.schemas import (
    AnalysisResponse, UploadHistoryItem, ErrorResponse,
    QueryRequest, QueryResponse, QueryHistoryItem
)
from app.db.models import UploadRecord, QueryRecord
from app.services.analyzer import analyze_dataframe, generate_summary
from app.services.rule_engine import run_rule_engine
from app.services.visualizer import generate_all_charts
from app.services.file_storage import save_uploaded_file

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
    description="Decision Intelligence System — Upload CSV data, get ranked insights, and ask questions about your data",
    version="2.0.0",
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
        
        # Save file to disk for later querying (Week 2)
        saved_name = save_uploaded_file(file.filename, contents)
        logger.info(f"Saved file for querying: {saved_name}")
        
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
    return {"status": "healthy", "service": "InsightFlow API", "version": "2.0.0"}


# ═══════════════════════════════════════════════════════════════
# ROUTE: POST /query — Natural Language Query (Week 2)
# ═══════════════════════════════════════════════════════════════
@app.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask a question about your data",
    description="Send a natural language question about a previously uploaded dataset. "
                "The system runs a 4-node pipeline: Query Understanding → Data Retrieval → "
                "Statistical Analysis → LLM Synthesis."
)
async def query_data(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """
    Natural language query endpoint.
    
    WHAT HAPPENS:
    1. User sends: {"query": "Why are sales dropping?", "filename": "sales.csv"}
    2. Pipeline runs 4 nodes:
       - Node 1: Understand the question (intent = trend_analysis)
       - Node 2: Load and filter the data
       - Node 3: Run OLS regression, find p-value
       - Node 4: Write plain-English explanation using the real numbers
    3. Response includes the explanation + all the underlying data
    
    WHY NOT JUST SEND THE CSV TO AN LLM?
    Because LLMs hallucinate numbers. Our pipeline ensures every
    statistic comes from actual computation (Node 3), not LLM generation.
    """
    from app.pipeline.graph import run_pipeline
    
    start_time = time.time()
    logger.info(f"Query: '{request.query}' on '{request.filename}'")
    
    # Run the 4-node pipeline
    result = await run_pipeline(request.query, request.filename)
    elapsed = time.time() - start_time
    
    # Save query to database
    try:
        query_record = QueryRecord(
            filename=request.filename,
            query=request.query,
            intent=result.get("query_context", {}).get("intent", "unknown"),
            confidence=result.get("confidence", "Unknown"),
            explanation=result.get("explanation", ""),
            pipeline_log_json=json.dumps(result.get("pipeline_log", [])),
        )
        db.add(query_record)
        db.commit()
        logger.info(f"Saved query record #{query_record.id}")
    except Exception as e:
        logger.error(f"Failed to save query record: {e}")
        db.rollback()
    
    return QueryResponse(
        explanation=result.get("explanation", "Analysis complete."),
        confidence=result.get("confidence", "Unknown"),
        confidence_reason=result.get("confidence_reason", ""),
        follow_up_questions=result.get("follow_up_questions", []),
        query_context=result.get("query_context", {}),
        analysis_result=result.get("analysis_result", {}),
        data_summary={
            "rows": result.get("data_slice", {}).get("rows", 0),
            "columns_used": result.get("data_slice", {}).get("columns_used", []),
            "summary_stats": result.get("data_slice", {}).get("summary_stats", {}),
        },
        pipeline_log=result.get("pipeline_log", []),
        elapsed_s=round(elapsed, 2),
        query=request.query,
        filename=request.filename,
    )


# ═══════════════════════════════════════════════════════════════
# ROUTE: GET /query/stream — SSE Streaming Query
# ═══════════════════════════════════════════════════════════════
@app.get(
    "/query/stream",
    summary="Stream query results via SSE",
    description="Sends real-time updates as each pipeline node completes. "
                "Use EventSource in the frontend to receive these events."
)
async def query_stream(
    query: str,
    filename: str,
):
    """
    SERVER-SENT EVENTS (SSE) Streaming endpoint.
    
    HOW SSE WORKS:
    1. Client opens a long-lived HTTP connection (using EventSource API)
    2. Server keeps the connection open and sends events as they happen
    3. Each event is formatted as: "data: {json}\n\n"
    4. Client receives events in real-time without polling
    
    DIFFERENCE FROM WEBSOCKETS:
    - SSE is one-directional (server → client only)
    - SSE uses standard HTTP (works through proxies, load balancers)
    - SSE auto-reconnects on failure
    - WebSockets are bidirectional (needed for chat, not for our use case)
    
    For our pipeline, SSE is perfect — we just need to push status
    updates as each node completes.
    """
    from app.pipeline.graph import run_pipeline_streaming
    
    async def event_generator():
        async for event in run_pipeline_streaming(query, filename):
            yield f"data: {json.dumps(event, default=str)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# ═══════════════════════════════════════════════════════════════
# ROUTE: GET /query/history — Query history
# ═══════════════════════════════════════════════════════════════
@app.get(
    "/query/history",
    response_model=list[QueryHistoryItem],
    summary="Get query history",
    description="Returns recent queries and their metadata"
)
def get_query_history(db: Session = Depends(get_db), limit: int = 20):
    """Returns past queries so users can review previous analysis sessions."""
    records = (
        db.query(QueryRecord)
        .order_by(QueryRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return records


# ═══════════════════════════════════════════════════════════════
# ROUTE: GET /files — List available datasets
# ═══════════════════════════════════════════════════════════════
@app.get("/files", summary="List uploaded datasets")
def list_files():
    """Returns list of uploaded CSV files available for querying."""
    from app.services.file_storage import get_available_files
    files = get_available_files()
    return {"files": files, "count": len(files)}
