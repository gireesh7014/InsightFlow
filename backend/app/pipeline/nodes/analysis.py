"""
NODE 3: STATISTICAL ANALYSIS — Real Numbers, Not Guesses
==========================================================
This is where InsightFlow separates from tutorial projects.
Every number in the output comes from an actual statistical test,
not from an LLM making up plausible-sounding statistics.

NO LLM IN THIS NODE — pure Python, pure math.

STATISTICAL TESTS USED:
  1. OLS Regression (statsmodels):
     Fits a line to the data. The slope tells us the trend direction
     and the p-value tells us if the trend is statistically significant.
     
  2. Pearson Correlation (scipy):
     Measures linear relationship between two variables.
     Returns r (strength) and p-value (significance).
     
  3. Z-score Anomaly Detection:
     Flags values more than 3 standard deviations from the mean.
     Simple but effective for normally-distributed data.
     (We'll add Isolation Forest in Week 3 for better detection.)
     
  4. T-test (scipy):
     Compares means of two groups. Tells you if the difference
     is statistically significant or just random noise.
     
  5. Descriptive Analysis:
     When no specific test applies, provide comprehensive descriptive stats.

WHAT IS A P-VALUE? (You WILL be asked this in interviews)
  The probability that the observed result happened by chance.
  - p < 0.05: Statistically significant (< 5% chance it's random)
  - p < 0.01: Highly significant
  - p > 0.05: NOT significant (could be random)
  
  Example: "Sales increased with p=0.02" means there's only a 2% 
  chance this increase is due to random noise. It's real.
"""

import time
import logging
import pandas as pd
import numpy as np
from scipy import stats
from app.pipeline.state import InsightState
from app.services.file_storage import load_dataframe

logger = logging.getLogger(__name__)

# Try importing statsmodels — it's optional for basic functionality
try:
    import statsmodels.api as sm
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    logger.warning("statsmodels not installed — OLS regression unavailable")


def _analyze_trend(df: pd.DataFrame, target_col: str, datetime_cols: list) -> dict:
    """
    Analyze the trend of a numeric column over time using OLS regression.
    
    OLS (Ordinary Least Squares) REGRESSION:
      Fits the best straight line through the data: y = mx + b
      - m (slope): positive = increasing trend, negative = decreasing
      - R² (r-squared): how well the line fits (0 = terrible, 1 = perfect)
      - p-value of slope: is the trend statistically significant?
    
    Returns:
        dict with trend direction, slope, p-value, R², and confidence interval
    """
    result = {"test_type": "trend_analysis"}
    
    try:
        series = df[target_col].dropna()
        if len(series) < 5:
            return {**result, "error": "Insufficient data for trend analysis (need 5+ points)"}
        
        # Create a numeric index (0, 1, 2, ...) for regression
        X = np.arange(len(series)).astype(float)
        y = series.values.astype(float)
        
        if HAS_STATSMODELS:
            # OLS with statsmodels — gives us p-values and confidence intervals
            X_with_const = sm.add_constant(X)  # Adds the intercept (b in y = mx + b)
            model = sm.OLS(y, X_with_const).fit()
            
            slope = float(model.params[1])
            p_value = float(model.pvalues[1])
            r_squared = float(model.rsquared)
            conf_int = model.conf_int()[1].tolist()  # 95% CI for slope
            
            result.update({
                "slope": round(slope, 4),
                "p_value": round(p_value, 6),
                "r_squared": round(r_squared, 4),
                "confidence_interval": [round(c, 4) for c in conf_int],
                "is_significant": p_value < 0.05,
            })
        else:
            # Fallback: scipy linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(X, y)
            result.update({
                "slope": round(float(slope), 4),
                "p_value": round(float(p_value), 6),
                "r_squared": round(float(r_value**2), 4),
                "is_significant": p_value < 0.05,
            })
        
        # Determine direction
        if p_value >= 0.05:
            direction = "stable"
            description = f"No statistically significant trend (p={p_value:.4f})"
        elif slope > 0:
            direction = "increasing"
            pct_change = ((y[-1] - y[0]) / abs(y[0])) * 100 if y[0] != 0 else 0
            description = f"Increasing trend (slope={slope:.4f}, p={p_value:.4f}). Overall change: {pct_change:.1f}%"
        else:
            direction = "decreasing"
            pct_change = ((y[-1] - y[0]) / abs(y[0])) * 100 if y[0] != 0 else 0
            description = f"Decreasing trend (slope={slope:.4f}, p={p_value:.4f}). Overall change: {pct_change:.1f}%"
        
        result.update({
            "trend_direction": direction,
            "description": description,
            "start_value": round(float(y[0]), 2),
            "end_value": round(float(y[-1]), 2),
            "mean": round(float(np.mean(y)), 2),
            "data_points": len(y),
        })
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Trend analysis failed: {e}")
    
    return result


def _analyze_correlation(df: pd.DataFrame, numeric_cols: list) -> dict:
    """
    Analyze correlations between numeric columns using Pearson r.
    
    PEARSON vs SPEARMAN:
    - Pearson: measures LINEAR relationships (assumes normal distribution)
    - Spearman: measures MONOTONIC relationships (works on ranks, no assumptions)
    
    We use Pearson because it's more interpretable, but mention when
    Spearman might be more appropriate (skewed data).
    """
    result = {"test_type": "correlation_analysis"}
    
    try:
        if len(numeric_cols) < 2:
            return {**result, "error": "Need at least 2 numeric columns for correlation analysis"}
        
        correlations = []
        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                col_a, col_b = numeric_cols[i], numeric_cols[j]
                data_a = df[col_a].dropna()
                data_b = df[col_b].dropna()
                
                # Align the two series (only use rows where both have values)
                common_idx = data_a.index.intersection(data_b.index)
                if len(common_idx) < 5:
                    continue
                
                r, p_value = stats.pearsonr(
                    data_a.loc[common_idx].values,
                    data_b.loc[common_idx].values
                )
                
                if abs(r) > 0.3:  # Only report meaningful correlations
                    correlations.append({
                        "column_a": col_a,
                        "column_b": col_b,
                        "r": round(float(r), 4),
                        "p_value": round(float(p_value), 6),
                        "is_significant": p_value < 0.05,
                        "strength": "strong" if abs(r) > 0.7 else "moderate" if abs(r) > 0.5 else "weak",
                        "direction": "positive" if r > 0 else "negative",
                    })
        
        correlations.sort(key=lambda x: abs(x["r"]), reverse=True)
        
        result.update({
            "correlations": correlations[:10],  # Top 10
            "n_significant": sum(1 for c in correlations if c["is_significant"]),
            "strongest": correlations[0] if correlations else None,
        })
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Correlation analysis failed: {e}")
    
    return result


def _detect_anomalies(df: pd.DataFrame, numeric_cols: list) -> dict:
    """
    Detect anomalies using Z-score method.
    
    Z-SCORE:
    z = (value - mean) / std_deviation
    
    Interpretation:
    - z = 0: value is exactly at the mean
    - z = 1: value is 1 std deviation above mean
    - z > 3: extremely unusual (only 0.3% of normal data)
    
    We flag |z| > 3 as anomalies. In Week 3, we'll add Isolation Forest
    which doesn't assume normal distribution.
    """
    result = {"test_type": "anomaly_detection"}
    
    try:
        all_anomalies = []
        
        for col in numeric_cols[:8]:  # Limit for performance
            series = df[col].dropna()
            if len(series) < 10:
                continue
            
            mean = series.mean()
            std = series.std()
            if std == 0:
                continue
            
            z_scores = (series - mean) / std
            anomaly_mask = z_scores.abs() > 3
            n_anomalies = anomaly_mask.sum()
            
            if n_anomalies > 0:
                anomaly_values = series[anomaly_mask]
                all_anomalies.append({
                    "column": col,
                    "count": int(n_anomalies),
                    "mean": round(float(mean), 2),
                    "std": round(float(std), 2),
                    "anomaly_values": [round(float(v), 2) for v in anomaly_values.head(5)],
                    "max_z_score": round(float(z_scores.abs().max()), 2),
                    "threshold": f"Beyond {mean - 3*std:.2f} to {mean + 3*std:.2f}",
                })
        
        result.update({
            "anomalies": all_anomalies,
            "total_anomalies": sum(a["count"] for a in all_anomalies),
            "columns_affected": len(all_anomalies),
        })
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Anomaly detection failed: {e}")
    
    return result


def _analyze_comparison(df: pd.DataFrame, numeric_cols: list, categorical_cols: list) -> dict:
    """
    Compare groups using groupby + descriptive stats + t-test.
    
    T-TEST:
    Compares means of two groups. Tests: "Is the difference real or random?"
    - p < 0.05: The groups are significantly different
    - p > 0.05: No significant difference (could be noise)
    
    Example: "North region mean sales = $1200, South = $900, p = 0.03"
    → The difference IS significant (only 3% chance it's random)
    """
    result = {"test_type": "comparison"}
    
    try:
        if not categorical_cols or not numeric_cols:
            return {**result, "error": "Need both categorical and numeric columns for comparison"}
        
        # Use the first categorical column with reasonable cardinality
        group_col = None
        for col in categorical_cols:
            n_unique = df[col].nunique()
            if 2 <= n_unique <= 10:
                group_col = col
                break
        
        if group_col is None:
            group_col = categorical_cols[0]
        
        target_col = numeric_cols[0]
        
        # Group statistics
        grouped = df.groupby(group_col)[target_col].agg(['mean', 'median', 'std', 'count'])
        grouped = grouped.round(2)
        
        group_stats = {}
        for group_name, row in grouped.iterrows():
            group_stats[str(group_name)] = {
                "mean": float(row['mean']),
                "median": float(row['median']),
                "std": float(row['std']),
                "count": int(row['count']),
            }
        
        # T-test between top 2 groups (by mean)
        t_test_result = None
        groups = list(grouped.index)
        if len(groups) >= 2:
            sorted_groups = grouped.sort_values('mean', ascending=False)
            g1_name = sorted_groups.index[0]
            g2_name = sorted_groups.index[-1]
            g1_data = df[df[group_col] == g1_name][target_col].dropna()
            g2_data = df[df[group_col] == g2_name][target_col].dropna()
            
            if len(g1_data) >= 3 and len(g2_data) >= 3:
                t_stat, p_value = stats.ttest_ind(g1_data, g2_data)
                t_test_result = {
                    "group_1": str(g1_name),
                    "group_2": str(g2_name),
                    "t_statistic": round(float(t_stat), 4),
                    "p_value": round(float(p_value), 6),
                    "is_significant": p_value < 0.05,
                    "mean_1": round(float(g1_data.mean()), 2),
                    "mean_2": round(float(g2_data.mean()), 2),
                    "difference": round(float(g1_data.mean() - g2_data.mean()), 2),
                }
        
        result.update({
            "group_column": group_col,
            "target_column": target_col,
            "group_stats": group_stats,
            "t_test": t_test_result,
            "n_groups": len(groups),
        })
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Comparison analysis failed: {e}")
    
    return result


def _analyze_summary(df: pd.DataFrame, numeric_cols: list, categorical_cols: list) -> dict:
    """General descriptive analysis when no specific test applies."""
    result = {"test_type": "descriptive_summary"}
    
    try:
        stats_dict = {}
        for col in numeric_cols[:8]:
            series = df[col].dropna()
            if len(series) == 0:
                continue
            stats_dict[col] = {
                "count": int(len(series)),
                "mean": round(float(series.mean()), 2),
                "median": round(float(series.median()), 2),
                "std": round(float(series.std()), 2),
                "min": round(float(series.min()), 2),
                "max": round(float(series.max()), 2),
                "skewness": round(float(series.skew()), 3),
                "range": round(float(series.max() - series.min()), 2),
            }
        
        cat_stats = {}
        for col in categorical_cols[:5]:
            vc = df[col].value_counts()
            cat_stats[col] = {
                "unique": int(df[col].nunique()),
                "top": str(vc.index[0]) if len(vc) > 0 else None,
                "top_pct": round(float(vc.iloc[0] / len(df) * 100), 1) if len(vc) > 0 else 0,
            }
        
        result.update({
            "numeric_stats": stats_dict,
            "categorical_stats": cat_stats,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "missing_total": int(df.isnull().sum().sum()),
        })
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


# ─── Intent → Analysis Mapping ───────────────────────────────
ANALYSIS_MAP = {
    "trend_analysis": _analyze_trend,
    "causal_analysis": _analyze_trend,  # Causal uses trend + correlation
    "correlation": _analyze_correlation,
    "anomaly_detection": _detect_anomalies,
    "comparison": _analyze_comparison,
    "summary": _analyze_summary,
    "forecasting": _analyze_trend,  # Basic trend for now
}


async def analysis_node(state: InsightState) -> dict:
    """
    NODE 3: Statistical Analysis
    
    Runs the appropriate statistical test based on the intent from Node 1.
    
    This node is the differentiator — every number comes from a real test.
    No LLM, no guessing, no hallucination.
    """
    start_time = time.time()
    query_context = state.get("query_context", {})
    data_slice = state.get("data_slice", {})
    filename = state["dataset_filename"]
    intent = query_context.get("intent", "summary")
    
    log_entry = {"node": "analysis", "status": "running"}
    
    try:
        # Load the actual DataFrame
        df = load_dataframe(filename)
        if df is None:
            raise ValueError(f"Dataset not found: {filename}")
        
        # Apply time filtering if data was filtered
        numeric_cols = data_slice.get("numeric_columns", list(df.select_dtypes(include='number').columns))
        categorical_cols = data_slice.get("categorical_columns", list(df.select_dtypes(include='object').columns))
        datetime_cols = data_slice.get("datetime_columns", [])
        
        # Run the appropriate analysis
        results = {}
        
        # Primary analysis based on intent
        if intent in ["trend_analysis", "causal_analysis", "forecasting"]:
            # Analyze trend for the most relevant numeric column
            target_col = numeric_cols[0] if numeric_cols else None
            # Check if query mentions a specific column
            relevant = query_context.get("relevant_columns", [])
            for col in relevant:
                if col in numeric_cols:
                    target_col = col
                    break
            
            if target_col:
                results["trend"] = _analyze_trend(df, target_col, datetime_cols)
            
            # For causal analysis, also add correlations
            if intent == "causal_analysis":
                results["correlations"] = _analyze_correlation(df, numeric_cols)
        
        elif intent == "correlation":
            results["correlations"] = _analyze_correlation(df, numeric_cols)
        
        elif intent == "anomaly_detection":
            results["anomalies"] = _detect_anomalies(df, numeric_cols)
        
        elif intent == "comparison":
            results["comparison"] = _analyze_comparison(df, numeric_cols, categorical_cols)
        
        else:
            results["summary"] = _analyze_summary(df, numeric_cols, categorical_cols)
        
        # Always add basic anomaly info (it's useful context)
        if "anomalies" not in results:
            anomaly_info = _detect_anomalies(df, numeric_cols[:3])
            if anomaly_info.get("total_anomalies", 0) > 0:
                results["anomaly_note"] = anomaly_info
        
        # Extract key findings as a list of strings
        key_findings = _extract_key_findings(results, intent)
        
        analysis_result = {
            "intent": intent,
            "results": results,
            "key_findings": key_findings,
            "columns_analyzed": numeric_cols[:8],
            "data_points": len(df),
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({
            "status": "complete",
            "duration_ms": duration_ms,
            "details": f"Ran {intent} analysis on {len(df)} rows, {len(key_findings)} findings",
        })
        
        logger.info(f"Node 3 complete: {intent}, {len(key_findings)} findings, {duration_ms}ms")
        
        return {
            "analysis_result": analysis_result,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({"status": "error", "duration_ms": duration_ms, "details": str(e)})
        logger.error(f"Node 3 failed: {e}")
        return {
            "analysis_result": {"error": str(e), "intent": intent},
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
            "error": f"Analysis failed: {str(e)}",
        }


def _extract_key_findings(results: dict, intent: str) -> list:
    """Extract human-readable key findings from analysis results."""
    findings = []
    
    # Trend findings
    trend = results.get("trend", {})
    if trend.get("trend_direction"):
        findings.append(trend["description"])
    
    # Correlation findings
    corr = results.get("correlations", {})
    if corr.get("strongest"):
        s = corr["strongest"]
        findings.append(
            f"Strongest correlation: {s['column_a']} and {s['column_b']} "
            f"(r={s['r']}, p={s['p_value']}, {s['strength']} {s['direction']})"
        )
    
    # Anomaly findings
    anomalies = results.get("anomalies", {})
    if anomalies.get("total_anomalies", 0) > 0:
        findings.append(
            f"Found {anomalies['total_anomalies']} anomalies across "
            f"{anomalies['columns_affected']} columns"
        )
    
    # Comparison findings
    comp = results.get("comparison", {})
    t_test = comp.get("t_test")
    if t_test:
        sig = "significantly" if t_test["is_significant"] else "not significantly"
        findings.append(
            f"{t_test['group_1']} (mean={t_test['mean_1']}) vs "
            f"{t_test['group_2']} (mean={t_test['mean_2']}): "
            f"{sig} different (p={t_test['p_value']})"
        )
    
    return findings
