"""
ANALYSIS ENGINE — Core Data Analysis with Pandas
=================================================
This is the computational heart of InsightFlow. It takes a raw CSV file
and produces structured statistics that the rule engine and visualizer consume.

WHAT PANDAS DOES HERE:
  pandas is the Python library for data manipulation. A DataFrame is like
  an Excel spreadsheet in memory — rows and columns with named headers.

KEY PANDAS OPERATIONS USED:
  - df.describe()  → generates count, mean, std, min, 25%, 50%, 75%, max
  - df.dtypes      → tells you the data type of each column
  - df.isnull()    → creates a True/False mask of missing values
  - df.corr()      → computes Pearson correlation between all numeric columns
  - df.skew()      → measures asymmetry of the distribution
  - df.nunique()   → counts unique values per column

STATISTICAL CONCEPTS:
  - Mean: Average value. Pulled by outliers (salary: $50k, $55k, $10M → mean = $3.4M, misleading!)
  - Median: Middle value when sorted. NOT pulled by outliers (median = $55k, much better!)
  - Std (Standard Deviation): How spread out the data is. Low std = data is clustered; high std = data is spread
  - Skewness: How lopsided the distribution is. 
    - Skew > 0: tail to the right (e.g., income distribution)
    - Skew < 0: tail to the left (e.g., exam scores with a hard ceiling)
    - |Skew| > 1.5: significantly skewed — median is more reliable than mean
  - Correlation: Linear relationship between two columns (-1 to +1)
    - +1: perfect positive (A goes up → B goes up)
    - -1: perfect negative (A goes up → B goes down)
    - 0: no linear relationship
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Any
from app.models.schemas import ColumnStats, CorrelationPair
import io
import logging

logger = logging.getLogger(__name__)


def detect_column_type(series: pd.Series) -> str:
    """
    Detect the semantic type of a column.
    
    pandas dtypes are technical (int64, float64, object).
    We convert them to human-readable categories:
      - 'numeric': integers and floats
      - 'categorical': strings, objects
      - 'datetime': dates and timestamps
      - 'boolean': true/false columns
    
    WHY NOT JUST USE pandas dtypes?
    A column of "1, 2, 3, 4, 5" might be truly numeric (like age)
    OR it might be a category encoded as integers (like rating 1-5).
    We use heuristics to make a best guess.
    """
    # Try to convert to datetime first (pandas often reads dates as 'object')
    if series.dtype == 'object':
        # Sample a few non-null values to check if they look like dates
        sample = series.dropna().head(20)
        if len(sample) > 0:
            try:
                pd.to_datetime(sample, infer_datetime_format=True)
                return 'datetime'
            except (ValueError, TypeError):
                pass
    
    # Check for datetime dtype
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'
    
    # Check for boolean
    if pd.api.types.is_bool_dtype(series):
        return 'boolean'
    
    # Check for numeric
    if pd.api.types.is_numeric_dtype(series):
        return 'numeric'
    
    # Everything else is categorical
    return 'categorical'


def compute_column_stats(df: pd.DataFrame) -> Tuple[List[ColumnStats], List[str], List[str], List[str]]:
    """
    Compute detailed statistics for every column in the DataFrame.
    
    Returns:
        - List of ColumnStats objects (one per column)
        - List of numeric column names
        - List of categorical column names
        - List of datetime column names
    
    HOW THIS WORKS:
    1. Loop through each column
    2. Detect its type (numeric/categorical/datetime)
    3. Compute type-appropriate statistics
    4. Package everything into ColumnStats objects
    """
    columns_stats = []
    numeric_cols = []
    categorical_cols = []
    datetime_cols = []
    
    for col_name in df.columns:
        series = df[col_name]
        col_type = detect_column_type(series)
        
        # Basic stats that apply to ALL column types
        total = len(series)
        missing = int(series.isnull().sum())
        missing_pct = round((missing / total) * 100, 2) if total > 0 else 0.0
        unique = int(series.nunique())
        
        # Initialize optional fields
        mean = median = std = min_val = max_val = skewness = None
        top_values = None
        
        if col_type == 'numeric':
            numeric_cols.append(col_name)
            # Convert to numeric, coercing errors to NaN
            numeric_series = pd.to_numeric(series, errors='coerce')
            
            # .describe() gives us most stats in one call (efficient!)
            desc = numeric_series.describe()
            
            mean = _safe_float(desc.get('mean'))
            std = _safe_float(desc.get('std'))
            min_val = _safe_float(desc.get('min'))
            max_val = _safe_float(desc.get('max'))
            median = _safe_float(numeric_series.median())
            
            # Skewness — measures distribution asymmetry
            # scipy's skew handles NaN better, but pandas .skew() is fine here
            try:
                skewness = _safe_float(numeric_series.skew())
            except Exception:
                skewness = None
                
        elif col_type == 'datetime':
            datetime_cols.append(col_name)
            
        else:
            categorical_cols.append(col_name)
            # Top 5 most frequent values
            value_counts = series.value_counts().head(5)
            top_values = [
                {"value": str(val), "count": int(count)}
                for val, count in value_counts.items()
            ]
        
        columns_stats.append(ColumnStats(
            name=col_name,
            dtype=col_type,
            total_count=total,
            missing_count=missing,
            missing_pct=missing_pct,
            unique_count=unique,
            mean=mean,
            median=median,
            std=std,
            min_val=min_val,
            max_val=max_val,
            skewness=skewness,
            top_values=top_values
        ))
    
    return columns_stats, numeric_cols, categorical_cols, datetime_cols


def compute_correlations(df: pd.DataFrame, numeric_cols: List[str]) -> Tuple[dict, List[CorrelationPair]]:
    """
    Compute the Pearson correlation matrix and extract notable pairs.
    
    WHAT IS A CORRELATION MATRIX?
    It's an N×N table where each cell shows how strongly two columns
    are linearly related. The diagonal is always 1.0 (a column is 
    perfectly correlated with itself).
    
    Example for columns [price, quantity, revenue]:
                 price  quantity  revenue
    price         1.00     -0.30     0.85
    quantity     -0.30      1.00     0.45  
    revenue       0.85      0.45     1.00
    
    Reading: price and revenue have r=0.85 (strong positive — when price
    goes up, revenue tends to go up too).
    
    WHY NOTABLE PAIRS?
    A 50-column dataset has 1225 correlations. We only surface the
    interesting ones (|r| > 0.5) so the user isn't overwhelmed.
    """
    if len(numeric_cols) < 2:
        return None, []
    
    # Compute correlation matrix
    # .corr() uses Pearson correlation by default
    corr_df = df[numeric_cols].corr()
    
    # Convert to nested dict for JSON serialization
    # {col_a: {col_b: correlation_value, ...}, ...}
    corr_matrix = {}
    for col in corr_df.columns:
        corr_matrix[col] = {
            other_col: _safe_float(corr_df.loc[col, other_col])
            for other_col in corr_df.columns
        }
    
    # Extract notable pairs (|r| > 0.5, excluding self-correlations)
    notable = []
    seen = set()  # Avoid duplicates (A↔B is same as B↔A)
    
    for i, col_a in enumerate(numeric_cols):
        for col_b in numeric_cols[i+1:]:  # Only upper triangle
            r = corr_df.loc[col_a, col_b]
            if pd.isna(r):
                continue
            
            abs_r = abs(r)
            if abs_r > 0.5:
                pair_key = tuple(sorted([col_a, col_b]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    
                    # Classify strength
                    if abs_r > 0.90:
                        strength = "very strong"
                    elif abs_r > 0.75:
                        strength = "strong"
                    elif abs_r > 0.5:
                        strength = "moderate"
                    else:
                        strength = "weak"
                    
                    notable.append(CorrelationPair(
                        column_a=col_a,
                        column_b=col_b,
                        correlation=round(float(r), 4),
                        strength=strength
                    ))
    
    # Sort by absolute correlation (most interesting first)
    notable.sort(key=lambda x: abs(x.correlation), reverse=True)
    
    return corr_matrix, notable


def compute_distributions(df: pd.DataFrame, numeric_cols: List[str]) -> dict:
    """
    Compute histogram data for numeric columns (used by Recharts in frontend).
    
    WHY NOT JUST SEND RAW DATA?
    A 100,000-row dataset would be huge as JSON. Instead, we compute
    histogram bins (typically 20-30 bins) and send just the bin counts.
    This is much smaller and Recharts can render it directly as a bar chart.
    
    HOW HISTOGRAMS WORK:
    1. Find the min and max of the data
    2. Divide that range into N equal bins
    3. Count how many values fall into each bin
    
    Example: data = [1, 2, 2, 3, 5, 8, 9]
    Bins: [1-3]: 4 values, [4-6]: 1 value, [7-9]: 2 values
    """
    distributions = {}
    
    for col in numeric_cols[:10]:  # Limit to first 10 columns for performance
        series = df[col].dropna()
        if len(series) < 2:
            continue
        
        try:
            # np.histogram computes bin edges and counts
            counts, bin_edges = np.histogram(series, bins=min(30, len(series) // 5 + 1))
            
            # Format for Recharts: [{range: "0-10", count: 5}, ...]
            hist_data = []
            for i in range(len(counts)):
                hist_data.append({
                    "range": f"{bin_edges[i]:.2f} - {bin_edges[i+1]:.2f}",
                    "min": round(float(bin_edges[i]), 2),
                    "max": round(float(bin_edges[i+1]), 2),
                    "count": int(counts[i])
                })
            
            distributions[col] = hist_data
        except Exception as e:
            logger.warning(f"Could not compute distribution for {col}: {e}")
            continue
    
    return distributions


def generate_summary(
    filename: str,
    row_count: int,
    column_count: int,
    numeric_cols: List[str],
    categorical_cols: List[str],
    datetime_cols: List[str],
    insights_summary: dict,
    notable_correlations: List[CorrelationPair]
) -> str:
    """
    Generate a plain-English summary of the dataset.
    
    This is NOT using an LLM — it's template-based. We'll add LLM-powered
    summaries in Week 2. But even a simple template-based summary is 
    surprisingly useful and beats showing raw numbers.
    """
    parts = []
    
    # Opening line
    parts.append(
        f"**{filename}** contains {row_count:,} rows and {column_count} columns."
    )
    
    # Column type breakdown
    type_parts = []
    if numeric_cols:
        type_parts.append(f"{len(numeric_cols)} numeric")
    if categorical_cols:
        type_parts.append(f"{len(categorical_cols)} categorical")
    if datetime_cols:
        type_parts.append(f"{len(datetime_cols)} datetime")
    if type_parts:
        parts.append(f"Column types: {', '.join(type_parts)}.")
    
    # Insight severity summary
    critical = insights_summary.get('critical', 0)
    warning = insights_summary.get('warning', 0)
    info = insights_summary.get('info', 0)
    
    if critical > 0:
        parts.append(
            f"⚠️ Found {critical} critical issue{'s' if critical > 1 else ''} "
            f"that need attention before analysis."
        )
    if warning > 0:
        parts.append(f"Found {warning} warning{'s' if warning > 1 else ''} worth reviewing.")
    if info > 0:
        parts.append(f"Identified {info} informational insight{'s' if info > 1 else ''}.")
    
    # Notable correlations
    if notable_correlations:
        top_corr = notable_correlations[0]
        direction = "positive" if top_corr.correlation > 0 else "negative"
        parts.append(
            f"Strongest relationship: {top_corr.column_a} and {top_corr.column_b} "
            f"show a {top_corr.strength} {direction} correlation (r={top_corr.correlation:.2f})."
        )
    
    return " ".join(parts)


def analyze_dataframe(df: pd.DataFrame, filename: str, file_size: int) -> dict:
    """
    Main analysis orchestrator — coordinates all analysis steps.
    
    This is the function that main.py calls. It:
    1. Computes column statistics
    2. Computes correlations
    3. Computes distributions (for frontend charts)
    4. Returns everything in a structured dict
    
    The rule engine and visualizer are called separately in main.py
    to keep each module focused on one job (Single Responsibility Principle).
    """
    row_count = len(df)
    column_count = len(df.columns)
    
    # Memory usage in MB
    memory_mb = round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
    
    # Step 1: Column statistics
    columns_stats, numeric_cols, categorical_cols, datetime_cols = compute_column_stats(df)
    
    # Step 2: Correlations (only if we have 2+ numeric columns)
    correlation_matrix, notable_correlations = compute_correlations(df, numeric_cols)
    
    # Step 3: Distributions for frontend charts
    distributions = compute_distributions(df, numeric_cols)
    
    return {
        "filename": filename,
        "file_size_bytes": file_size,
        "row_count": row_count,
        "column_count": column_count,
        "memory_usage_mb": memory_mb,
        "columns": columns_stats,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "datetime_columns": datetime_cols,
        "correlation_matrix": correlation_matrix,
        "notable_correlations": notable_correlations,
        "distributions": distributions,
    }


def _safe_float(value) -> float:
    """
    Safely convert a value to float, handling NaN and infinity.
    
    WHY THIS EXISTS:
    pandas can produce NaN (Not a Number) or infinity values.
    JSON doesn't support NaN or infinity, so we must convert them to None.
    Without this, your API would crash with a serialization error.
    """
    if value is None:
        return None
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 4)
    except (ValueError, TypeError):
        return None
