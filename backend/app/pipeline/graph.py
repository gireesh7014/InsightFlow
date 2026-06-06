"""
LANGGRAPH ASSEMBLY — Wiring the 4 Nodes Into a Pipeline
=========================================================
This file creates the LangGraph state graph and compiles it
into an executable pipeline.

HOW LANGGRAPH WORKS:
  1. Define a StateGraph with a TypedDict as the state shape
  2. Add nodes — each is a Python function that reads/writes state
  3. Add edges — define the execution order
  4. Compile — creates a runnable pipeline

  Think of it as a production assembly line:
  ┌───────────┐    ┌───────────┐    ┌──────────┐    ┌───────────┐
  │ Node 1:   │───→│ Node 2:   │───→│ Node 3:  │───→│ Node 4:   │
  │ Understand│    │ Retrieve  │    │ Analyze  │    │ Synthesize│
  │ the query │    │ the data  │    │ the stats│    │ the answer│
  └───────────┘    └───────────┘    └──────────┘    └───────────┘
       ↓                ↓                ↓                ↓
  QueryContext      DataSlice      AnalysisResult    Explanation

WHY LANGGRAPH OVER PLAIN FUNCTION CALLS?
  You could just call the 4 functions sequentially. LangGraph adds:
  1. State management — shared state between nodes
  2. Streaming — emit events as each node completes
  3. Error handling — graph-level error recovery
  4. Observability — built-in logging of each step
  5. Extensibility — easy to add conditional branches, loops, parallel nodes
"""

import logging
import time
from typing import AsyncIterator
from langgraph.graph import StateGraph, END
from app.pipeline.state import InsightState
from app.pipeline.nodes.query_understanding import query_understanding_node
from app.pipeline.nodes.data_retrieval import data_retrieval_node
from app.pipeline.nodes.analysis import analysis_node
from app.pipeline.nodes.synthesis import synthesis_node

logger = logging.getLogger(__name__)


def build_pipeline() -> StateGraph:
    """
    Build and compile the 4-node LangGraph pipeline.
    
    GRAPH STRUCTURE:
      START → query_understanding → data_retrieval → analysis → synthesis → END
    
    Each node receives the entire state dict and returns a partial dict
    with the fields it wants to update. LangGraph merges the updates.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the state graph with our InsightState schema
    graph = StateGraph(InsightState)
    
    # ─── Add Nodes ────────────────────────────────────────
    # Each node is a function: (state: InsightState) → dict
    graph.add_node("query_understanding", query_understanding_node)
    graph.add_node("data_retrieval", data_retrieval_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("synthesis", synthesis_node)
    
    # ─── Add Edges (execution order) ──────────────────────
    # set_entry_point: which node runs first
    graph.set_entry_point("query_understanding")
    
    # Linear pipeline: 1 → 2 → 3 → 4 → END
    graph.add_edge("query_understanding", "data_retrieval")
    graph.add_edge("data_retrieval", "analysis")
    graph.add_edge("analysis", "synthesis")
    graph.add_edge("synthesis", END)
    
    # ─── Compile ──────────────────────────────────────────
    # Compile converts the graph definition into a runnable object
    compiled = graph.compile()
    
    logger.info("LangGraph pipeline compiled: query_understanding → data_retrieval → analysis → synthesis")
    return compiled


# ─── Compiled pipeline (singleton) ────────────────────────────
# We compile once and reuse for every query
_pipeline = None


def get_pipeline():
    """Get the compiled pipeline (lazy initialization)."""
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


async def run_pipeline(query: str, filename: str) -> dict:
    """
    Execute the full pipeline for a user query.
    
    This is the main function called by the API endpoint.
    
    Args:
        query: Natural language question about the data
        filename: Name of the uploaded CSV file
    
    Returns:
        Complete pipeline state with all node outputs
    """
    pipeline = get_pipeline()
    
    # Initial state
    initial_state = {
        "user_query": query,
        "dataset_filename": filename,
        "pipeline_log": [],
    }
    
    start_time = time.time()
    logger.info(f"Pipeline starting: query='{query}', file='{filename}'")
    
    try:
        # Run the pipeline
        # ainvoke() runs all nodes in sequence, passing state between them
        result = await pipeline.ainvoke(initial_state)
        
        elapsed = time.time() - start_time
        logger.info(f"Pipeline complete in {elapsed:.2f}s")
        
        return result
    
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Pipeline failed after {elapsed:.2f}s: {e}")
        return {
            **initial_state,
            "error": str(e),
            "explanation": f"Pipeline failed: {str(e)}. Please try a different question.",
            "confidence": "Low",
            "confidence_reason": f"Pipeline error: {str(e)}",
        }


async def run_pipeline_streaming(query: str, filename: str) -> AsyncIterator[dict]:
    """
    Execute the pipeline with streaming — emit events as each node completes.
    
    SSE (Server-Sent Events) STREAMING:
    Instead of waiting for the entire pipeline to finish, we send
    updates to the frontend as each node completes:
    
    1. "query_understanding starting..."  → "complete" (100ms)
    2. "data_retrieval starting..."       → "complete" (200ms)
    3. "analysis starting..."             → "complete" (500ms)
    4. "synthesis starting..."            → "complete" (1000ms)
    
    This makes the system feel responsive — the user sees progress
    instead of staring at a spinner for 2 seconds.
    
    TECHNICAL: This is an async generator (async def + yield).
    Each yield sends one SSE event to the client.
    """
    pipeline = get_pipeline()
    
    initial_state = {
        "user_query": query,
        "dataset_filename": filename,
        "pipeline_log": [],
    }
    
    start_time = time.time()
    
    # Yield initial event
    yield {
        "type": "pipeline_start",
        "query": query,
        "filename": filename,
    }
    
    try:
        # Stream through the pipeline
        # astream() yields the state after each node completes
        node_names = ["query_understanding", "data_retrieval", "analysis", "synthesis"]
        
        async for event in pipeline.astream(initial_state):
            # event contains the updated state after each node
            elapsed = time.time() - start_time
            
            # Determine which node just completed by checking pipeline_log
            log = event.get("pipeline_log", [])
            if log:
                last_entry = log[-1]
                yield {
                    "type": "node_complete",
                    "node": last_entry.get("node", "unknown"),
                    "status": last_entry.get("status", "unknown"),
                    "duration_ms": last_entry.get("duration_ms", 0),
                    "details": last_entry.get("details", ""),
                    "elapsed_s": round(elapsed, 2),
                }
            
            # If this is the final state (has explanation), yield it
            if "explanation" in event:
                yield {
                    "type": "pipeline_complete",
                    "explanation": event.get("explanation", ""),
                    "confidence": event.get("confidence", ""),
                    "confidence_reason": event.get("confidence_reason", ""),
                    "follow_up_questions": event.get("follow_up_questions", []),
                    "query_context": event.get("query_context", {}),
                    "analysis_result": event.get("analysis_result", {}),
                    "data_slice_summary": {
                        "rows": event.get("data_slice", {}).get("rows", 0),
                        "columns_used": event.get("data_slice", {}).get("columns_used", []),
                    },
                    "pipeline_log": event.get("pipeline_log", []),
                    "elapsed_s": round(time.time() - start_time, 2),
                }
    
    except Exception as e:
        yield {
            "type": "pipeline_error",
            "error": str(e),
            "elapsed_s": round(time.time() - start_time, 2),
        }
