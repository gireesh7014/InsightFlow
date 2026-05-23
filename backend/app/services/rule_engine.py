"""
RULE ENGINE — 20 Hardcoded Insight Rules
=========================================
This is the "secret sauce" of Week 1. Before any ML, before any LLM,
these simple conditional rules make your project look genuinely intelligent.

WHY RULES BEFORE ML?
  1. Rules are explainable: "Missing > 40% → critical" is transparent
  2. Rules are fast: no model loading, no inference time
  3. Rules are reliable: no randomness, no hallucination
  4. Rules work on ANY dataset: no training required
  
  In production, many companies use rules alongside ML models.
  The rules catch known patterns; ML catches novel ones.

HOW THE SCORING WORKS:
  Each insight gets a severity (critical/warning/info) and a score (0-1).
  Score determines ranking WITHIN the same severity level.
  
  Sorting order: critical (high score first) → warning (high score first) → info

RULE CATEGORIES:
  1. Data Quality (missing data, duplicates, constant columns)
  2. Distribution (skewness, outliers)
  3. Relationships (correlation, potential causality)
  4. Data Type issues (encoding, mixed types)
  5. Dataset shape (small data, wide data)
"""

import pandas as pd
import numpy as np
from typing import List
from app.models.schemas import Insight, ColumnStats, CorrelationPair
import logging

logger = logging.getLogger(__name__)


def run_rule_engine(
    df: pd.DataFrame,
    columns_stats: List[ColumnStats],
    numeric_cols: List[str],
    categorical_cols: List[str],
    datetime_cols: List[str],
    notable_correlations: List[CorrelationPair]
) -> List[Insight]:
    """
    Run all 20 rules against the dataset and return ranked insights.
    
    Each rule is a separate function that returns 0 or more Insight objects.
    This makes it easy to add/remove/modify rules independently.
    
    Args:
        df: The full DataFrame
        columns_stats: Pre-computed column statistics
        numeric_cols: List of numeric column names
        categorical_cols: List of categorical column names
        datetime_cols: List of datetime column names
        notable_correlations: Pre-computed correlation pairs
    
    Returns:
        List of Insight objects, sorted by severity then score
    """
    insights = []
    
    # Run each rule and collect insights
    # Each rule function appends to the insights list
    insights.extend(_rule_missing_critical(columns_stats))        # Rule 1
    insights.extend(_rule_missing_warning(columns_stats))         # Rule 2
    insights.extend(_rule_missing_info(columns_stats))            # Rule 3
    insights.extend(_rule_skewness_high(columns_stats))           # Rule 4
    insights.extend(_rule_skewness_moderate(columns_stats))       # Rule 5
    insights.extend(_rule_correlation_extreme(notable_correlations))  # Rule 6
    insights.extend(_rule_correlation_strong(notable_correlations))   # Rule 7
    insights.extend(_rule_zero_variance(columns_stats))           # Rule 8
    insights.extend(_rule_outliers(df, numeric_cols))             # Rule 9
    insights.extend(_rule_high_cardinality(columns_stats, categorical_cols))  # Rule 10
    insights.extend(_rule_datetime_detected(datetime_cols))       # Rule 11
    insights.extend(_rule_integer_categorical(df, numeric_cols))  # Rule 12
    insights.extend(_rule_negative_values(df, numeric_cols))      # Rule 13
    insights.extend(_rule_class_imbalance(df, categorical_cols))  # Rule 14
    insights.extend(_rule_duplicate_rows(df))                     # Rule 15
    insights.extend(_rule_dominant_value(df, columns_stats))      # Rule 16
    insights.extend(_rule_small_dataset(df))                      # Rule 17
    insights.extend(_rule_wide_dataset(df))                       # Rule 18
    insights.extend(_rule_perfect_correlation(notable_correlations))  # Rule 19
    insights.extend(_rule_all_missing_column(columns_stats))      # Rule 20
    
    # Sort: critical first, then warning, then info
    # Within same severity, higher score first
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    insights.sort(key=lambda x: (severity_order.get(x.severity, 3), -x.score))
    
    return insights


# ═══════════════════════════════════════════════════════════════
# RULE 1: Missing data > 40% → CRITICAL
# ═══════════════════════════════════════════════════════════════
def _rule_missing_critical(columns_stats: List[ColumnStats]) -> List[Insight]:
    """
    WHY CRITICAL AT 40%?
    Above 40% missing, imputation (filling in values) becomes unreliable.
    The "filled in" values are more guesses than data. Any ML model
    trained on this will be learning from mostly fabricated data.
    
    WHAT TO DO: Consider dropping the column entirely, or flagging
    that analyses involving this column are low-confidence.
    """
    results = []
    for col in columns_stats:
        if col.missing_pct > 40:
            results.append(Insight(
                severity="critical",
                category="missing_data",
                message=f"Column '{col.name}' has {col.missing_pct:.1f}% missing values — too sparse for reliable analysis",
                column=col.name,
                details=f"{col.missing_count} out of {col.total_count} values are missing. "
                        f"Consider dropping this column or using domain-specific imputation.",
                score=min(col.missing_pct / 100, 1.0)  # Higher missing% = higher score
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 2: Missing data 20-40% → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_missing_warning(columns_stats: List[ColumnStats]) -> List[Insight]:
    """
    20-40% missing is workable but risky. Imputation methods like
    mean/median filling or KNN imputation can help, but you should
    report that the analysis has reduced confidence.
    """
    results = []
    for col in columns_stats:
        if 20 < col.missing_pct <= 40:
            results.append(Insight(
                severity="warning",
                category="missing_data",
                message=f"Column '{col.name}' has {col.missing_pct:.1f}% missing values — will reduce model reliability",
                column=col.name,
                details=f"Imputation recommended. For numeric data, consider median imputation. "
                        f"For categorical, consider mode imputation or a 'missing' category.",
                score=col.missing_pct / 100
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 3: Missing data 5-20% → INFO
# ═══════════════════════════════════════════════════════════════
def _rule_missing_info(columns_stats: List[ColumnStats]) -> List[Insight]:
    """Minor missing data is common and usually easy to handle."""
    results = []
    for col in columns_stats:
        if 5 < col.missing_pct <= 20:
            results.append(Insight(
                severity="info",
                category="missing_data",
                message=f"Column '{col.name}' has {col.missing_pct:.1f}% missing values — minor gap, easily imputable",
                column=col.name,
                details=None,
                score=col.missing_pct / 100
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 4: High skewness (|skew| > 2.0) → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_skewness_high(columns_stats: List[ColumnStats]) -> List[Insight]:
    """
    WHAT IS SKEWNESS?
    Imagine a bell curve (normal distribution). Skewness measures
    how much that curve is "leaning" to one side.
    
    Right-skewed (skew > 0): Long tail to the right
      Example: Income distribution — most people earn moderate amounts,
      few earn extremely high. Mean > Median.
    
    Left-skewed (skew < 0): Long tail to the left
      Example: Age at retirement — most retire around 60-65,
      few retire very young. Mean < Median.
    
    WHY IT MATTERS:
    Many statistical methods (t-tests, linear regression) assume data
    is roughly normally distributed. Highly skewed data violates this
    assumption and can produce misleading results.
    
    WHAT TO DO: Log transform, Box-Cox transform, or use robust
    methods that don't assume normality.
    """
    results = []
    for col in columns_stats:
        if col.skewness is not None and abs(col.skewness) > 2.0:
            direction = "right" if col.skewness > 0 else "left"
            results.append(Insight(
                severity="warning",
                category="skewness",
                message=f"Column '{col.name}' is heavily {direction}-skewed (skew={col.skewness:.2f}) — median is more reliable than mean",
                column=col.name,
                details=f"Mean: {col.mean:.2f}, Median: {col.median:.2f}. "
                        f"The {'mean is inflated by high values' if col.skewness > 0 else 'mean is deflated by low values'}. "
                        f"Consider log transformation for modeling." if col.mean is not None and col.median is not None else None,
                score=min(abs(col.skewness) / 5, 1.0)
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 5: Moderate skewness (1.0-2.0) → INFO
# ═══════════════════════════════════════════════════════════════
def _rule_skewness_moderate(columns_stats: List[ColumnStats]) -> List[Insight]:
    results = []
    for col in columns_stats:
        if col.skewness is not None and 1.0 < abs(col.skewness) <= 2.0:
            direction = "right" if col.skewness > 0 else "left"
            results.append(Insight(
                severity="info",
                category="skewness",
                message=f"Column '{col.name}' is moderately {direction}-skewed (skew={col.skewness:.2f})",
                column=col.name,
                details=None,
                score=abs(col.skewness) / 5
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 6: Near-perfect correlation (|r| > 0.90) → CRITICAL
# ═══════════════════════════════════════════════════════════════
def _rule_correlation_extreme(correlations: List[CorrelationPair]) -> List[Insight]:
    """
    WHAT IS MULTICOLLINEARITY?
    When two columns are almost perfectly correlated (|r| > 0.9),
    they carry nearly the same information. In ML:
    - Linear regression becomes unstable (coefficients explode)
    - Feature importance becomes misleading
    - Model trains slower without learning more
    
    FIX: Drop one of the two columns, or combine them (PCA).
    """
    results = []
    for pair in correlations:
        if abs(pair.correlation) > 0.90:
            results.append(Insight(
                severity="critical",
                category="correlation",
                message=f"Near-perfect correlation ({pair.correlation:.2f}) between '{pair.column_a}' and '{pair.column_b}' — likely redundant or derived",
                column=f"{pair.column_a}, {pair.column_b}",
                details="Consider dropping one column to avoid multicollinearity. "
                        "If one is derived from the other (e.g., price × quantity = revenue), keep the original.",
                score=abs(pair.correlation)
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 7: Strong correlation (0.75-0.90) → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_correlation_strong(correlations: List[CorrelationPair]) -> List[Insight]:
    """
    Strong but not perfect correlation often indicates a real relationship.
    This is actually useful information — it might reveal causal links
    or business patterns.
    """
    results = []
    for pair in correlations:
        if 0.75 < abs(pair.correlation) <= 0.90:
            direction = "positive" if pair.correlation > 0 else "negative"
            results.append(Insight(
                severity="warning",
                category="correlation",
                message=f"Strong {direction} correlation ({pair.correlation:.2f}) between '{pair.column_a}' and '{pair.column_b}' — possible causal link",
                column=f"{pair.column_a}, {pair.column_b}",
                details=f"When '{pair.column_a}' increases, '{pair.column_b}' tends to "
                        f"{'increase' if pair.correlation > 0 else 'decrease'}. "
                        f"Investigate if this is a causal relationship or a confound.",
                score=abs(pair.correlation)
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 8: Zero variance columns → CRITICAL
# ═══════════════════════════════════════════════════════════════
def _rule_zero_variance(columns_stats: List[ColumnStats]) -> List[Insight]:
    """
    A column with zero variance has the same value in every row.
    It carries zero information and should be dropped.
    Example: A "country" column where every row says "India".
    """
    results = []
    zero_var_cols = [col.name for col in columns_stats if col.unique_count <= 1]
    if zero_var_cols:
        results.append(Insight(
            severity="critical",
            category="zero_variance",
            message=f"{len(zero_var_cols)} column(s) have zero variance (constant value) — will be dropped automatically",
            column=", ".join(zero_var_cols),
            details=f"Columns: {', '.join(zero_var_cols)}. These contain the same value in every row and provide no information for analysis.",
            score=0.9
        ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 9: Outliers beyond 3 standard deviations → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_outliers(df: pd.DataFrame, numeric_cols: List[str]) -> List[Insight]:
    """
    WHAT IS THE 3-SIGMA RULE?
    In a normal distribution:
      - 68% of data falls within 1σ of the mean
      - 95% within 2σ
      - 99.7% within 3σ
    
    So values beyond 3σ are extremely rare (0.3%). If you see many
    of them, either:
      a) The data isn't normally distributed (check skewness)
      b) There are genuine outliers (measurement errors, fraud, etc.)
    
    WHY THIS MATTERS FOR ML:
    Outliers can dominate the training process — a single extreme value
    can pull a regression line way off. Tree-based models (Random Forest,
    XGBoost) are more robust to outliers than linear models.
    """
    results = []
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        
        mean = series.mean()
        std = series.std()
        if std == 0:
            continue
        
        # Count values beyond 3 standard deviations
        outlier_mask = (series - mean).abs() > 3 * std
        n_outliers = outlier_mask.sum()
        
        if n_outliers > 0:
            pct = (n_outliers / len(series)) * 100
            results.append(Insight(
                severity="warning",
                category="outliers",
                message=f"Column '{col}' has {n_outliers} extreme outlier(s) beyond 3σ ({pct:.1f}% of data)",
                column=col,
                details=f"Mean: {mean:.2f}, Std: {std:.2f}. "
                        f"Values beyond [{mean - 3*std:.2f}, {mean + 3*std:.2f}] are flagged. "
                        f"Consider Isolation Forest for robust anomaly detection (Week 3).",
                score=min(pct / 10, 1.0)
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 10: High cardinality in categorical columns → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_high_cardinality(columns_stats: List[ColumnStats], categorical_cols: List[str]) -> List[Insight]:
    """
    WHAT IS CARDINALITY?
    The number of unique values in a categorical column.
    Low cardinality: gender (2-3 values) — easy to encode
    High cardinality: city names (1000s of values) — problematic
    
    WHY IT MATTERS:
    One-hot encoding a column with 1000 unique values creates 1000
    new columns. This explodes memory and can cause overfitting.
    Solutions: target encoding, frequency encoding, or embedding.
    """
    results = []
    for col in columns_stats:
        if col.name in categorical_cols and col.unique_count > 50:
            results.append(Insight(
                severity="warning",
                category="high_cardinality",
                message=f"Column '{col.name}' has {col.unique_count} unique values — may need special encoding before modeling",
                column=col.name,
                details="One-hot encoding would create too many columns. "
                        "Consider target encoding, frequency encoding, or embeddings.",
                score=min(col.unique_count / 500, 1.0)
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 11: Datetime column detected → INFO
# ═══════════════════════════════════════════════════════════════
def _rule_datetime_detected(datetime_cols: List[str]) -> List[Insight]:
    """Presence of datetime columns means time series analysis is possible."""
    results = []
    if datetime_cols:
        results.append(Insight(
            severity="info",
            category="datetime",
            message=f"Time series analysis available — {len(datetime_cols)} datetime column(s) detected: {', '.join(datetime_cols)}",
            column=", ".join(datetime_cols),
            details="Trend detection (STL decomposition), seasonality analysis, "
                    "and forecasting can be performed on these columns.",
            score=0.7
        ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 12: All-integer column might be categorical → INFO
# ═══════════════════════════════════════════════════════════════
def _rule_integer_categorical(df: pd.DataFrame, numeric_cols: List[str]) -> List[Insight]:
    """
    A column of [1, 2, 3, 4, 5] could be a rating (categorical) or
    a count (numeric). If there are few unique integers, it's likely
    categorical and should be treated differently.
    """
    results = []
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 5:
            continue
        
        # Check: all values are integers and unique count is low
        is_all_int = (series == series.astype(int)).all() if series.dtype in ['float64', 'float32'] else pd.api.types.is_integer_dtype(series)
        
        if is_all_int and series.nunique() <= 10 and series.nunique() < len(series) * 0.05:
            results.append(Insight(
                severity="info",
                category="encoding",
                message=f"Column '{col}' looks like a categorical encoded as integer ({series.nunique()} unique values)",
                column=col,
                details=f"Unique values: {sorted(series.unique().tolist())[:10]}. "
                        f"If these represent categories (e.g., ratings), convert to categorical type for proper analysis.",
                score=0.5
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 13: Negative values in typically-positive columns → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_negative_values(df: pd.DataFrame, numeric_cols: List[str]) -> List[Insight]:
    """
    Some columns should logically never be negative (price, count, age).
    Negatives might indicate data entry errors or special encodings.
    """
    # Columns that typically shouldn't have negatives
    positive_keywords = ['price', 'cost', 'amount', 'count', 'quantity', 'age', 
                         'salary', 'revenue', 'sales', 'weight', 'height', 'distance']
    
    results = []
    for col in numeric_cols:
        col_lower = col.lower()
        if any(kw in col_lower for kw in positive_keywords):
            series = df[col].dropna()
            n_negative = (series < 0).sum()
            if n_negative > 0:
                results.append(Insight(
                    severity="warning",
                    category="data_quality",
                    message=f"Column '{col}' contains {n_negative} negative value(s) — check if this is expected",
                    column=col,
                    details=f"Column name suggests positive values only. "
                            f"Negative values might indicate returns, refunds, corrections, or data entry errors.",
                    score=0.6
                ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 14: Class imbalance (>5:1 ratio) → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_class_imbalance(df: pd.DataFrame, categorical_cols: List[str]) -> List[Insight]:
    """
    WHAT IS CLASS IMBALANCE?
    If you're classifying fraud vs not-fraud, and 99% of data is "not fraud",
    a model that ALWAYS predicts "not fraud" gets 99% accuracy but is useless.
    
    WHY IT MATTERS:
    ML models tend to predict the majority class because that minimizes error.
    Solutions: SMOTE (generates synthetic minority samples), class weights,
    or use metrics like F1-score instead of accuracy.
    """
    results = []
    # Check columns with low cardinality (likely targets)
    for col in categorical_cols:
        series = df[col].dropna()
        if 2 <= series.nunique() <= 10:  # Likely a classification target
            value_counts = series.value_counts()
            majority = value_counts.iloc[0]
            minority = value_counts.iloc[-1]
            
            if minority > 0:
                ratio = majority / minority
                if ratio > 5:
                    results.append(Insight(
                        severity="warning",
                        category="class_imbalance",
                        message=f"Class imbalance detected in '{col}' ({ratio:.0f}:1 ratio) — use SMOTE or class weights if used as target",
                        column=col,
                        details=f"Most common: '{value_counts.index[0]}' ({majority} rows). "
                                f"Least common: '{value_counts.index[-1]}' ({minority} rows). "
                                f"If this is your prediction target, accuracy alone is misleading.",
                        score=min(ratio / 20, 1.0)
                    ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 15: Duplicate rows > 5% → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_duplicate_rows(df: pd.DataFrame) -> List[Insight]:
    """
    Duplicate rows can indicate data collection errors (same record
    entered twice) or valid repetitions (multiple purchases by same customer).
    Either way, it's worth flagging.
    """
    results = []
    n_duplicates = df.duplicated().sum()
    if n_duplicates > 0:
        pct = (n_duplicates / len(df)) * 100
        if pct > 5:
            results.append(Insight(
                severity="warning",
                category="duplicates",
                message=f"{n_duplicates} duplicate rows found ({pct:.1f}%) — verify if intentional",
                column=None,
                details="Duplicate rows can inflate statistics and bias ML models. "
                        "If unintentional, deduplicate before analysis.",
                score=min(pct / 20, 1.0)
            ))
        elif pct > 1:
            results.append(Insight(
                severity="info",
                category="duplicates",
                message=f"{n_duplicates} duplicate rows found ({pct:.1f}%)",
                column=None,
                details=None,
                score=pct / 20
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 16: Single value dominant (>95% same value) → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_dominant_value(df: pd.DataFrame, columns_stats: List[ColumnStats]) -> List[Insight]:
    """
    If 95%+ of a column has the same value, the column is nearly constant.
    It provides almost no information for ML but isn't quite zero-variance.
    """
    results = []
    for col_stat in columns_stats:
        series = df[col_stat.name].dropna()
        if len(series) == 0:
            continue
        
        most_common_count = series.value_counts().iloc[0] if len(series.value_counts()) > 0 else 0
        dominance_pct = (most_common_count / len(series)) * 100
        
        if dominance_pct > 95 and col_stat.unique_count > 1:
            results.append(Insight(
                severity="warning",
                category="low_variance",
                message=f"Column '{col_stat.name}' has {dominance_pct:.1f}% identical values — near-constant, limited analytical value",
                column=col_stat.name,
                details=f"The value '{series.value_counts().index[0]}' dominates. "
                        f"Consider dropping this column for most analyses.",
                score=dominance_pct / 100
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 17: Small dataset (<50 rows) → WARNING
# ═══════════════════════════════════════════════════════════════
def _rule_small_dataset(df: pd.DataFrame) -> List[Insight]:
    """
    STATISTICAL SIGNIFICANCE AND SAMPLE SIZE:
    With fewer than 50 rows, many statistical tests become unreliable.
    Correlation coefficients are noisy, distributions are hard to estimate,
    and ML models will overfit easily.
    
    The Central Limit Theorem says sample means approximate a normal
    distribution when n ≥ 30, so 50 gives us a small safety margin.
    """
    results = []
    if len(df) < 50:
        results.append(Insight(
            severity="warning",
            category="sample_size",
            message=f"Only {len(df)} rows — trend analysis needs 50+ for statistical significance. Showing descriptive stats only.",
            column=None,
            details="Small datasets have high variance in statistics. "
                    "Correlation, regression, and distribution analyses may not be reliable.",
            score=0.8
        ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 18: Wide dataset (columns > rows) → INFO
# ═══════════════════════════════════════════════════════════════
def _rule_wide_dataset(df: pd.DataFrame) -> List[Insight]:
    """
    THE CURSE OF DIMENSIONALITY:
    When you have more features (columns) than samples (rows),
    ML models can find spurious patterns. It's like having more
    unknowns than equations — there are infinite "solutions."
    
    Fix: Feature selection, PCA, or collect more data.
    """
    results = []
    if len(df.columns) > len(df):
        results.append(Insight(
            severity="info",
            category="dimensionality",
            message=f"Wide dataset: {len(df.columns)} columns vs {len(df)} rows — curse of dimensionality risk",
            column=None,
            details="More features than samples can cause overfitting. "
                    "Consider feature selection or dimensionality reduction (PCA).",
            score=0.6
        ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 19: Perfect correlation (r = 1.0 or -1.0) → CRITICAL
# ═══════════════════════════════════════════════════════════════
def _rule_perfect_correlation(correlations: List[CorrelationPair]) -> List[Insight]:
    """
    Perfect correlation means one column is an exact linear function
    of another. Common examples:
    - Celsius and Fahrenheit (F = 1.8C + 32)
    - Total = subtotal + tax
    
    One must be dropped — they are 100% redundant.
    """
    results = []
    for pair in correlations:
        if abs(pair.correlation) >= 0.99:
            results.append(Insight(
                severity="critical",
                category="correlation",
                message=f"Perfect correlation ({pair.correlation:.4f}) between '{pair.column_a}' and '{pair.column_b}' — one is likely derived from the other",
                column=f"{pair.column_a}, {pair.column_b}",
                details="These columns carry identical information. Drop one to avoid redundancy.",
                score=1.0
            ))
    return results


# ═══════════════════════════════════════════════════════════════
# RULE 20: Entirely empty column → CRITICAL
# ═══════════════════════════════════════════════════════════════
def _rule_all_missing_column(columns_stats: List[ColumnStats]) -> List[Insight]:
    """A column with 100% missing values provides nothing. Drop it."""
    results = []
    empty_cols = [col.name for col in columns_stats if col.missing_pct >= 99.9]
    if empty_cols:
        results.append(Insight(
            severity="critical",
            category="missing_data",
            message=f"{len(empty_cols)} column(s) are entirely empty — should be dropped",
            column=", ".join(empty_cols),
            details=f"Columns: {', '.join(empty_cols)}. These contain no data.",
            score=1.0
        ))
    return results
