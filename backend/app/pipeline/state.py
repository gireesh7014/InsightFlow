"""
PIPELINE STATE — Shared State for the LangGraph Pipeline
=========================================================
This defines the data structure that flows through all 4 nodes.

WHAT IS A STATE GRAPH?
  LangGraph uses a "state graph" — a workflow where:
  1. Each node is a Python function
  2. Nodes share a common state dictionary
  3. Each node reads from state, processes data, and WRITES BACK to state
  4. The graph defines which node runs next

  Think of it like an assembly line in a factory:
  - The product (state) moves along the line
  - Each station (node) adds something to the product
  - At the end, you have a finished product

WHY TypedDict?
  TypedDict gives us type hints for dictionary keys.
  Unlike a regular dict, your IDE can autocomplete state["query_context"]
  and catch typos before runtime.

IMPORTANT DESIGN DECISION:
  State carries DATA OBJECTS (DataFrames, stats), not strings.
  This is what separates InsightFlow from tutorial projects where
  agents just pass text between LLM calls.
"""

from typing import TypedDict, Optional, List, Annotated
import operator


class InsightState(TypedDict, total=False):
    """
    The shared state that flows through all 4 pipeline nodes.
    
    Each node reads what it needs and writes its output.
    The `total=False` means all fields are optional — nodes
    only set the fields they're responsible for.
    
    DATA FLOW:
      Input → Node 1 sets query_context
            → Node 2 sets data_slice
            → Node 3 sets analysis_result
            → Node 4 sets explanation
    """
    
    # ─── Input (set before pipeline starts) ───────────────
    user_query: str                    # "Why are sales dropping in Q3?"
    dataset_filename: str              # "sales_sample.csv"
    
    # ─── Node 1 Output: Query Understanding ───────────────
    # What the user is asking about, in structured form
    query_context: dict
    # Example: {
    #   "intent": "trend_analysis",
    #   "relevant_columns": ["sales_amount", "date"],
    #   "time_range": {"start": "2024-07", "end": "2024-09"},
    #   "comparison_groups": null,
    #   "confidence": 0.9,
    #   "method": "keyword"  # or "llm"
    # }
    
    # ─── Node 2 Output: Data Retrieval ────────────────────
    # Filtered and enriched data ready for analysis
    data_slice: dict
    # Contains:
    # - "rows": number of rows after filtering
    # - "columns_used": list of column names
    # - "data_sample": first 5 rows as list of dicts (for display)
    # - "summary_stats": per-column stats for the filtered data
    # - "derived_features": any computed features (rolling avg, etc.)
    
    # ─── Node 3 Output: Statistical Analysis ──────────────
    # Real numbers from actual statistical tests
    analysis_result: dict
    # Contains:
    # - "test_type": "ols_regression" | "pearson_correlation" | "t_test" | etc.
    # - "metrics": {p_value, r_squared, coefficient, etc.}
    # - "anomalies": list of anomalous rows
    # - "trend_direction": "increasing" | "decreasing" | "stable"
    # - "key_findings": list of finding strings with numbers
    
    # ─── Node 4 Output: Synthesis ─────────────────────────
    explanation: str                   # Plain-English explanation
    follow_up_questions: list          # Suggested follow-up questions
    confidence: str                    # "High" | "Medium" | "Low"
    confidence_reason: str             # Why this confidence level
    
    # ─── Pipeline Metadata ────────────────────────────────
    pipeline_log: list                 # Step-by-step audit trail
    # Each entry: {"node": "query_understanding", "status": "complete", 
    #              "duration_ms": 45, "details": "..."}
    
    charts: dict                       # Any charts generated during analysis
    error: str                         # Error message if something fails
