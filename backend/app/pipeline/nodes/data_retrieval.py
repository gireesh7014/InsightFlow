"""
NODE 2: DATA RETRIEVAL — Fetch & Prepare Data for Analysis
============================================================
Takes the QueryContext from Node 1 and produces a filtered,
enriched DataFrame ready for statistical analysis.

THIS NODE IS PURE PYTHON — NO LLM.
  The QueryContext tells us which columns and time ranges to use.
  This node does the actual data manipulation:
  1. Filter rows by time range
  2. Select relevant columns
  3. Compute derived features (rolling averages, period-over-period change)
  4. Output: actual data as a dict (not a description of data)

PANDAS CONCEPTS USED:
  - df.loc[] — filter rows and select columns by label
  - pd.to_datetime() — convert strings to datetime objects
  - df.rolling(window) — compute rolling (moving) averages
  - df.pct_change() — compute percentage change between rows
  - df.groupby() — split data into groups for comparison
  - df.resample() — group time-series data by time period (day, week, month)
"""

import time
import logging
import pandas as pd
import numpy as np
from app.pipeline.state import InsightState
from app.services.file_storage import load_dataframe

logger = logging.getLogger(__name__)


def _filter_by_time(df: pd.DataFrame, time_range: dict, datetime_cols: list) -> pd.DataFrame:
    """
    Filter the DataFrame by the time range extracted from the query.
    
    WHAT IS DATETIME INDEXING?
    When a DataFrame has a datetime column, we can filter it like:
      df[df['date'] >= '2024-07-01']  → all rows from July 2024 onward
    
    pandas understands date strings and can compare them with datetime objects.
    """
    if not time_range or not datetime_cols:
        return df
    
    dt_col = datetime_cols[0]
    df_copy = df.copy()
    
    try:
        df_copy[dt_col] = pd.to_datetime(df_copy[dt_col], errors='coerce')
        
        if "year" in time_range:
            df_copy = df_copy[df_copy[dt_col].dt.year == time_range["year"]]
        
        if "month" in time_range:
            df_copy = df_copy[df_copy[dt_col].dt.month == time_range["month"]]
        
        if "month_start" in time_range and "month_end" in time_range:
            df_copy = df_copy[
                (df_copy[dt_col].dt.month >= time_range["month_start"]) &
                (df_copy[dt_col].dt.month <= time_range["month_end"])
            ]
        
        if "quarter" in time_range:
            df_copy = df_copy[df_copy[dt_col].dt.quarter == time_range["quarter"]]
        
        logger.info(f"Time filter: {len(df)} → {len(df_copy)} rows")
    except Exception as e:
        logger.warning(f"Time filtering failed: {e}")
        return df
    
    return df_copy


def _compute_derived_features(df: pd.DataFrame, numeric_cols: list, datetime_cols: list) -> dict:
    """
    Compute derived features that help with analysis.
    
    FEATURE ENGINEERING:
    Raw data often isn't enough for analysis. We compute:
    
    1. ROLLING AVERAGES (moving averages):
       Smooths out short-term fluctuations to reveal trends.
       Example: 7-day rolling average of sales removes daily noise.
       
    2. PERCENTAGE CHANGE:
       How much a value changed from the previous row.
       Useful for detecting sudden spikes or drops.
       
    3. PERIOD AGGREGATION:
       Group by month/quarter to see higher-level patterns.
    """
    derived = {}
    
    if datetime_cols and len(df) > 5:
        dt_col = datetime_cols[0]
        try:
            df_sorted = df.copy()
            df_sorted[dt_col] = pd.to_datetime(df_sorted[dt_col], errors='coerce')
            df_sorted = df_sorted.sort_values(dt_col).dropna(subset=[dt_col])
            
            for col in numeric_cols[:5]:  # Limit for performance
                series = df_sorted[col].dropna()
                if len(series) < 5:
                    continue
                
                # Rolling average (window = 20% of data, min 3)
                window = max(3, len(series) // 5)
                rolling_avg = series.rolling(window=window, min_periods=1).mean()
                
                # Period-over-period change
                pct_change = series.pct_change().dropna()
                
                derived[col] = {
                    "rolling_avg_last": round(float(rolling_avg.iloc[-1]), 2) if len(rolling_avg) > 0 else None,
                    "rolling_avg_first": round(float(rolling_avg.iloc[0]), 2) if len(rolling_avg) > 0 else None,
                    "avg_pct_change": round(float(pct_change.mean() * 100), 2) if len(pct_change) > 0 else None,
                    "max_spike": round(float(pct_change.max() * 100), 2) if len(pct_change) > 0 else None,
                    "max_drop": round(float(pct_change.min() * 100), 2) if len(pct_change) > 0 else None,
                }
        except Exception as e:
            logger.warning(f"Derived feature computation failed: {e}")
    
    return derived


async def data_retrieval_node(state: InsightState) -> dict:
    """
    NODE 2: Data Retrieval
    
    Takes QueryContext from Node 1 and prepares the actual data
    for statistical analysis in Node 3.
    
    Steps:
    1. Load the full DataFrame from storage
    2. Filter by time range (if specified in the query)
    3. Select relevant columns
    4. Compute derived features (rolling averages, % changes)
    5. Generate summary statistics for the filtered data
    6. Output structured data (NOT a description — actual numbers)
    """
    start_time = time.time()
    query_context = state.get("query_context", {})
    filename = state["dataset_filename"]
    
    log_entry = {"node": "data_retrieval", "status": "running"}
    
    try:
        # ─── Step 1: Load DataFrame ──────────────────────
        df = load_dataframe(filename)
        if df is None:
            raise ValueError(f"Dataset '{filename}' not found. Please re-upload.")
        
        original_rows = len(df)
        
        # Detect column types
        datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
        # Also check object columns that might be dates
        for col in df.select_dtypes(include='object').columns:
            try:
                pd.to_datetime(df[col].dropna().head(5))
                datetime_cols.append(col)
            except (ValueError, TypeError):
                pass
        
        numeric_cols = list(df.select_dtypes(include='number').columns)
        categorical_cols = list(df.select_dtypes(include='object').columns)
        categorical_cols = [c for c in categorical_cols if c not in datetime_cols]
        
        # ─── Step 2: Filter by time range ────────────────
        time_range = query_context.get("time_range")
        df_filtered = _filter_by_time(df, time_range, datetime_cols)
        
        # ─── Step 3: Select relevant columns ─────────────
        relevant_cols = query_context.get("relevant_columns", [])
        # Always include datetime columns for context
        columns_used = list(set(relevant_cols + datetime_cols))
        if not columns_used:
            columns_used = list(df_filtered.columns)
        
        # ─── Step 4: Compute derived features ────────────
        derived = _compute_derived_features(df_filtered, numeric_cols, datetime_cols)
        
        # ─── Step 5: Summary statistics for filtered data ─
        summary_stats = {}
        for col in numeric_cols:
            if col in df_filtered.columns:
                series = df_filtered[col].dropna()
                if len(series) > 0:
                    summary_stats[col] = {
                        "count": int(len(series)),
                        "mean": round(float(series.mean()), 2),
                        "median": round(float(series.median()), 2),
                        "std": round(float(series.std()), 2),
                        "min": round(float(series.min()), 2),
                        "max": round(float(series.max()), 2),
                        "total": round(float(series.sum()), 2),
                    }
        
        # Categorical summaries
        for col in categorical_cols:
            if col in df_filtered.columns:
                vc = df_filtered[col].value_counts()
                summary_stats[col] = {
                    "unique_values": int(df_filtered[col].nunique()),
                    "top_value": str(vc.index[0]) if len(vc) > 0 else None,
                    "top_count": int(vc.iloc[0]) if len(vc) > 0 else 0,
                    "distribution": {str(k): int(v) for k, v in vc.head(10).items()},
                }
        
        # ─── Step 6: Sample data for display ─────────────
        data_sample = df_filtered.head(5).fillna("N/A").to_dict(orient='records')
        
        # Build output
        data_slice = {
            "rows": len(df_filtered),
            "original_rows": original_rows,
            "was_filtered": len(df_filtered) != original_rows,
            "columns_used": columns_used,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "datetime_columns": datetime_cols,
            "data_sample": data_sample,
            "summary_stats": summary_stats,
            "derived_features": derived,
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({
            "status": "complete",
            "duration_ms": duration_ms,
            "details": f"Loaded {len(df_filtered)}/{original_rows} rows, {len(numeric_cols)} numeric cols",
        })
        
        logger.info(f"Node 2 complete: {len(df_filtered)} rows, {len(numeric_cols)} numeric, {duration_ms}ms")
        
        return {
            "data_slice": data_slice,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({"status": "error", "duration_ms": duration_ms, "details": str(e)})
        logger.error(f"Node 2 failed: {e}")
        return {
            "data_slice": {"rows": 0, "error": str(e)},
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            "error": f"Data retrieval failed: {str(e)}",
        }
