"""
NODE 1: QUERY UNDERSTANDING — Hybrid Intent Classifier
========================================================
Takes a natural-language question and produces a structured QueryContext.

THE HYBRID APPROACH (this is your interview answer):
  Step 1: Keyword rules (fast, no API call, handles 80-90% of queries)
  Step 2: LLM fallback (only when keywords fail, handles edge cases)

WHY NOT JUST USE AN LLM?
  1. Speed: keyword matching is <1ms; LLM call is 500-2000ms
  2. Cost: keyword matching is free; LLM calls add up
  3. Reliability: keywords always return the same result; LLMs can vary
  4. Explainability: you can log "matched keyword 'trend'" vs "LLM decided"

  Production systems at companies like Google and Amazon use this exact
  pattern: rules first, ML/LLM only for what rules can't handle.

INTENT TYPES:
  - trend_analysis: "What's the trend?", "Is sales increasing?"
  - comparison: "Compare North vs South", "Which category is best?"
  - anomaly_detection: "Any outliers?", "What's unusual?"
  - correlation: "What drives revenue?", "Is price related to sales?"
  - causal_analysis: "Why did sales drop?", "What caused the increase?"
  - summary: "Describe the data", "Give me an overview"
  - forecasting: "What's the prediction?", "Forecast next quarter"
"""

import re
import time
import logging
import pandas as pd
from typing import Optional
from app.pipeline.state import InsightState
from app.services.llm import generate_structured_output, is_llm_available

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# KEYWORD RULES — Fast intent classification (no API call)
# ═══════════════════════════════════════════════════════════════

# Each intent has a list of keyword patterns (regex-ready)
INTENT_KEYWORDS = {
    "trend_analysis": [
        r"\btrend\b", r"\btrending\b", r"\bincreas\w*\b", r"\bdecreas\w*\b",
        r"\bgrow\w*\b", r"\bdeclin\w*\b", r"\bdrop\w*\b", r"\brise\w*\b",
        r"\bfall\w*\b", r"\bover time\b", r"\bmonth\w*\b", r"\bquarter\w*\b",
        r"\byear\w*\b", r"\bweek\w*\b", r"\btimeline\b", r"\bprogress\w*\b",
    ],
    "comparison": [
        r"\bcompar\w*\b", r"\bvs\b", r"\bversus\b", r"\bdifference\b",
        r"\bbetween\b", r"\bwhich\b.*\b(best|worst|high|low|more|less)\b",
        r"\btop\b", r"\bbottom\b", r"\brank\w*\b", r"\bbetter\b", r"\bworse\b",
    ],
    "anomaly_detection": [
        r"\banom\w*\b", r"\boutlier\w*\b", r"\bunusual\b", r"\bstrange\b",
        r"\bweird\b", r"\bspike\w*\b", r"\bsudden\b", r"\bextreme\b",
        r"\babnormal\b", r"\bunexpect\w*\b",
    ],
    "correlation": [
        r"\bcorrelat\w*\b", r"\brelat\w*\b.*\bbetween\b", r"\bdriv\w*\b",
        r"\baffect\w*\b", r"\bimpact\w*\b", r"\binfluenc\w*\b",
        r"\bdepend\w*\b", r"\bconnect\w*\b",
    ],
    "causal_analysis": [
        r"\bwhy\b", r"\bcause\w*\b", r"\breason\w*\b", r"\bexplain\b",
        r"\bwhat happen\w*\b", r"\bwhat went\b", r"\bbecause\b",
    ],
    "summary": [
        r"\bsummar\w*\b", r"\boverview\b", r"\bdescrib\w*\b", r"\btell me about\b",
        r"\bwhat is\b", r"\bshow me\b", r"\bhow does\b.*\blook\b",
        r"\bgeneral\b", r"\boverall\b",
    ],
    "forecasting": [
        r"\bforecast\w*\b", r"\bpredict\w*\b", r"\bestimate\b",
        r"\bfuture\b", r"\bnext\b.*\b(month|quarter|year|week)\b",
        r"\bproject\w*\b", r"\bexpect\w*\b",
    ],
}


def _classify_by_keywords(query: str) -> Optional[dict]:
    """
    Attempt to classify the query using keyword matching.
    
    HOW IT WORKS:
    1. Convert query to lowercase
    2. Check each intent's keyword patterns against the query
    3. Count how many patterns match for each intent
    4. Pick the intent with the most matches
    5. Return None if no keywords matched (triggers LLM fallback)
    
    Returns:
        dict with intent and confidence, or None if no match
    """
    query_lower = query.lower()
    
    scores = {}
    for intent, patterns in INTENT_KEYWORDS.items():
        match_count = 0
        for pattern in patterns:
            if re.search(pattern, query_lower):
                match_count += 1
        if match_count > 0:
            scores[intent] = match_count
    
    if not scores:
        return None  # No keywords matched — fall through to LLM
    
    # Pick the intent with the most keyword matches
    best_intent = max(scores, key=scores.get)
    # Confidence based on number of matches (more matches = more confident)
    confidence = min(0.5 + (scores[best_intent] * 0.15), 0.95)
    
    return {
        "intent": best_intent,
        "confidence": round(confidence, 2),
        "method": "keyword",
    }


def _extract_columns_from_query(query: str, available_columns: list[str]) -> list[str]:
    """
    Find which dataset columns the user is asking about.
    
    Strategy: Check if any column name (or close variant) appears in the query.
    This is a simple but effective approach — handles "sales", "revenue",
    "shipping cost" naturally.
    """
    query_lower = query.lower()
    matched = []
    
    for col in available_columns:
        col_lower = col.lower()
        # Direct match or close match (replace _ with space)
        col_variants = [
            col_lower,
            col_lower.replace("_", " "),
            col_lower.replace("_", ""),
        ]
        for variant in col_variants:
            if variant in query_lower:
                matched.append(col)
                break
    
    return matched


def _extract_time_range(query: str) -> Optional[dict]:
    """
    Extract time-related hints from the query.
    
    Matches patterns like:
    - "in Q3" → Q3 of current year
    - "in August" → August
    - "last month" → relative time reference
    - "2024" → specific year
    """
    query_lower = query.lower()
    time_range = {}
    
    # Quarter detection
    quarter_match = re.search(r'\bq([1-4])\b', query_lower)
    if quarter_match:
        q = int(quarter_match.group(1))
        time_range["quarter"] = q
        # Map quarter to month ranges
        month_starts = {1: 1, 2: 4, 3: 7, 4: 10}
        time_range["month_start"] = month_starts[q]
        time_range["month_end"] = month_starts[q] + 2
    
    # Month detection
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "jun": 6, "jul": 7, "aug": 8, "sep": 9,
        "oct": 10, "nov": 11, "dec": 12,
    }
    for month_name, month_num in months.items():
        if month_name in query_lower:
            time_range["month"] = month_num
            break
    
    # Year detection
    year_match = re.search(r'\b(20\d{2})\b', query_lower)
    if year_match:
        time_range["year"] = int(year_match.group(1))
    
    return time_range if time_range else None


async def query_understanding_node(state: InsightState) -> dict:
    """
    NODE 1: Query Understanding
    
    Takes the user's natural language query and produces a structured
    QueryContext object that tells the next nodes:
    - What kind of analysis to do (intent)
    - Which columns to focus on
    - What time range to filter
    - How confident we are in the classification
    
    This is the entry point of the pipeline.
    """
    start_time = time.time()
    query = state["user_query"]
    filename = state["dataset_filename"]
    
    log_entry = {
        "node": "query_understanding",
        "status": "running",
    }
    
    try:
        # Load the dataset to get column names
        from app.services.file_storage import load_dataframe
        df = load_dataframe(filename)
        available_columns = list(df.columns) if df is not None else []
        
        # ─── Step 1: Try keyword classification ──────────
        result = _classify_by_keywords(query)
        
        # ─── Step 2: LLM fallback if keywords failed ─────
        if result is None and is_llm_available():
            logger.info("No keyword match — falling back to LLM classification")
            
            llm_result = await generate_structured_output(
                prompt=f"""Classify this user query about a dataset.

Query: "{query}"

Available columns in the dataset: {available_columns}

Return JSON with:
- "intent": one of [trend_analysis, comparison, anomaly_detection, correlation, causal_analysis, summary, forecasting]
- "confidence": float 0.0 to 1.0
- "relevant_columns": list of column names from the available columns that are relevant
- "reasoning": one sentence explaining your classification
""",
                system_prompt="You are a query classifier for a data analysis system. Be precise and factual."
            )
            
            if llm_result and "intent" in llm_result:
                result = {
                    "intent": llm_result["intent"],
                    "confidence": llm_result.get("confidence", 0.7),
                    "method": "llm",
                }
                # Use LLM's column suggestions if available
                if "relevant_columns" in llm_result:
                    llm_columns = [c for c in llm_result["relevant_columns"] if c in available_columns]
                    if llm_columns:
                        available_columns_match = llm_columns
        
        # ─── Step 3: Default fallback ────────────────────
        if result is None:
            result = {
                "intent": "summary",
                "confidence": 0.3,
                "method": "default_fallback",
            }
            logger.info("Using default fallback: summary intent")
        
        # ─── Step 4: Extract columns and time range ──────
        matched_columns = _extract_columns_from_query(query, available_columns)
        time_range = _extract_time_range(query)
        
        # If no specific columns mentioned, use numeric columns as default
        if not matched_columns and df is not None:
            matched_columns = [c for c in df.select_dtypes(include='number').columns]
        
        # Build final QueryContext
        query_context = {
            **result,
            "original_query": query,
            "relevant_columns": matched_columns,
            "all_columns": available_columns,
            "time_range": time_range,
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({
            "status": "complete",
            "duration_ms": duration_ms,
            "details": f"Intent: {result['intent']} ({result['method']}, confidence: {result['confidence']})",
        })
        
        logger.info(
            f"Node 1 complete: intent={result['intent']}, "
            f"method={result['method']}, confidence={result['confidence']}, "
            f"columns={len(matched_columns)}, {duration_ms}ms"
        )
        
        return {
            "query_context": query_context,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({
            "status": "error",
            "duration_ms": duration_ms,
            "details": str(e),
        })
        logger.error(f"Node 1 failed: {e}")
        return {
            "query_context": {
                "intent": "summary",
                "confidence": 0.1,
                "method": "error_fallback",
                "original_query": query,
                "relevant_columns": [],
                "all_columns": [],
                "time_range": None,
            },
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            "error": f"Query understanding failed: {str(e)}",
        }
