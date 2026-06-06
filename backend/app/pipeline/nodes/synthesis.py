"""
NODE 4: SYNTHESIS — LLM as a Writer, Not an Analyst
=====================================================
This is the ONLY node where the LLM creates the final output.
But critically: it doesn't analyze data. It WRITES about data
that was already analyzed by Node 3.

THE KEY PRINCIPLE:
  Node 3 produces numbers: "slope=−42.3, p=0.02, R²=0.67"
  Node 4 translates: "Sales are declining by $42/period, and this
  trend is statistically significant (p=0.02). The trend explains
  67% of the variation in the data."

  The LLM is a WRITER, not an ANALYST.
  If the LLM is unavailable, we still produce a useful response
  using template-based fallback.

WHY THIS MATTERS:
  - LLMs hallucinate statistics. They make up numbers.
  - By forcing the LLM to use ONLY the numbers from Node 3,
    we prevent hallucination.
  - System prompt: "Use only the numbers provided. Do not invent statistics."
"""

import time
import logging
import json
from app.pipeline.state import InsightState
from app.services.llm import generate_text, is_llm_available

logger = logging.getLogger(__name__)

# ─── System Prompt — Controls LLM Behavior ───────────────────
SYNTHESIS_SYSTEM_PROMPT = """You are a data analyst explaining findings to a business user.

STRICT RULES:
1. Use ONLY the numbers provided in the analysis results. Do NOT invent any statistics.
2. Every claim must reference a specific number from the data.
3. Use plain English — no jargon without explanation.
4. Structure: Start with the main finding, then supporting evidence, then recommendation.
5. Be concise — 3-5 sentences for the main explanation.
6. If results show "not significant" (p > 0.05), say so honestly.
7. Never say "the data shows" without citing the specific number.

FORMAT:
- Start with a bold one-line summary
- Follow with 2-3 sentences of evidence with numbers
- End with a practical recommendation
"""


def _build_synthesis_prompt(state: InsightState) -> str:
    """
    Build the prompt that tells the LLM what to explain.
    
    This is PROMPT ENGINEERING — constructing the input to get
    the best output from the LLM. Key techniques:
    1. Context injection: provide the actual data and results
    2. Format specification: tell it exactly how to structure the response
    3. Constraint specification: explicitly say what NOT to do
    """
    query = state.get("user_query", "")
    query_context = state.get("query_context", {})
    data_slice = state.get("data_slice", {})
    analysis_result = state.get("analysis_result", {})
    
    prompt = f"""The user asked: "{query}"

Intent classified as: {query_context.get('intent', 'unknown')}

Data Overview:
- Dataset: {state.get('dataset_filename', 'unknown')}
- Rows analyzed: {data_slice.get('rows', 'unknown')}
- Columns used: {', '.join(data_slice.get('columns_used', [])[:10])}

Analysis Results:
{json.dumps(analysis_result.get('results', {}), indent=2, default=str)[:3000]}

Key Findings:
{chr(10).join(f'- {f}' for f in analysis_result.get('key_findings', []))}

Summary Statistics:
{json.dumps(data_slice.get('summary_stats', {}), indent=2, default=str)[:2000]}

Derived Features:
{json.dumps(data_slice.get('derived_features', {}), indent=2, default=str)[:1000]}

Now write a clear, concise explanation answering the user's question.
Use ONLY the numbers above. Do NOT make up any statistics.
Also suggest 2-3 follow-up questions the user might want to ask.
Format follow-ups as a JSON array at the end, like:
FOLLOW_UPS: ["question 1", "question 2", "question 3"]
"""
    return prompt


def _determine_confidence(state: InsightState) -> tuple:
    """
    Determine the confidence level of our answer.
    
    Confidence is NOT a float — it's always one of three labels
    with a one-sentence explanation. This shows you understand
    the limits of your own system.
    """
    data_slice = state.get("data_slice", {})
    analysis_result = state.get("analysis_result", {})
    query_context = state.get("query_context", {})
    
    rows = data_slice.get("rows", 0)
    intent_confidence = query_context.get("confidence", 0.5)
    results = analysis_result.get("results", {})
    
    # Check for issues that reduce confidence
    issues = []
    
    if rows < 50:
        issues.append(f"small dataset ({rows} rows)")
    
    if intent_confidence < 0.5:
        issues.append("uncertain query interpretation")
    
    # Check for high missing data
    stats = data_slice.get("summary_stats", {})
    for col, col_stats in stats.items():
        if isinstance(col_stats, dict) and col_stats.get("count", 0) > 0:
            total = data_slice.get("original_rows", rows)
            if total > 0 and col_stats.get("count", total) / total < 0.7:
                issues.append(f"significant missing data in {col}")
                break
    
    # Check if analysis had errors
    if analysis_result.get("error"):
        issues.append("analysis encountered errors")
    
    # Check p-value significance
    trend = results.get("trend", {})
    if trend.get("p_value") and trend["p_value"] > 0.05:
        issues.append("trend not statistically significant")
    
    # Determine level
    if len(issues) == 0 and rows >= 100 and intent_confidence >= 0.7:
        return "High", f"Complete data (n={rows}), clear query, significant results"
    elif len(issues) <= 1:
        reason = issues[0] if issues else "moderate data quality"
        return "Medium", f"Mostly reliable — {reason}"
    else:
        return "Low", f"Multiple concerns: {', '.join(issues[:3])}"


def _fallback_synthesis(state: InsightState) -> str:
    """
    Generate a response without the LLM (template-based).
    
    This ensures the system is useful even without an API key.
    Real production systems always have fallbacks.
    """
    analysis_result = state.get("analysis_result", {})
    key_findings = analysis_result.get("key_findings", [])
    data_slice = state.get("data_slice", {})
    
    parts = []
    parts.append(f"**Analysis of {state.get('dataset_filename', 'your data')}** ({data_slice.get('rows', '?')} rows analyzed)")
    parts.append("")
    
    if key_findings:
        parts.append("**Key Findings:**")
        for finding in key_findings:
            parts.append(f"• {finding}")
    else:
        parts.append("No significant findings detected in the data for this query.")
    
    # Add stats summary
    stats = data_slice.get("summary_stats", {})
    if stats:
        parts.append("")
        parts.append("**Quick Stats:**")
        for col, col_stats in list(stats.items())[:5]:
            if isinstance(col_stats, dict) and "mean" in col_stats:
                parts.append(f"• {col}: mean={col_stats['mean']}, median={col_stats.get('median', 'N/A')}")
    
    return "\n".join(parts)


async def synthesis_node(state: InsightState) -> dict:
    """
    NODE 4: Synthesis
    
    Takes all the structured data from Nodes 1-3 and produces
    a plain-English explanation that a non-technical user can understand.
    
    If the LLM is available: uses Gemini to write a natural explanation
    If not: uses template-based fallback (still useful!)
    """
    start_time = time.time()
    log_entry = {"node": "synthesis", "status": "running"}
    
    try:
        # Determine confidence
        confidence, confidence_reason = _determine_confidence(state)
        
        # Generate explanation
        if is_llm_available():
            prompt = _build_synthesis_prompt(state)
            raw_response = await generate_text(prompt, SYNTHESIS_SYSTEM_PROMPT)
            
            # Parse follow-up questions from response
            follow_ups = []
            explanation = raw_response
            
            if "FOLLOW_UPS:" in raw_response:
                parts = raw_response.split("FOLLOW_UPS:")
                explanation = parts[0].strip()
                try:
                    follow_ups_text = parts[1].strip()
                    follow_ups = json.loads(follow_ups_text)
                except (json.JSONDecodeError, IndexError):
                    follow_ups = []
        else:
            explanation = _fallback_synthesis(state)
            # Generate template-based follow-ups
            intent = state.get("query_context", {}).get("intent", "summary")
            follow_ups = _generate_fallback_followups(intent, state)
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({
            "status": "complete",
            "duration_ms": duration_ms,
            "details": f"Generated explanation ({len(explanation)} chars), {len(follow_ups)} follow-ups",
        })
        
        logger.info(f"Node 4 complete: {len(explanation)} chars, confidence={confidence}, {duration_ms}ms")
        
        return {
            "explanation": explanation,
            "follow_up_questions": follow_ups[:3],
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry.update({"status": "error", "duration_ms": duration_ms, "details": str(e)})
        logger.error(f"Node 4 failed: {e}")
        
        return {
            "explanation": _fallback_synthesis(state),
            "follow_up_questions": [],
            "confidence": "Low",
            "confidence_reason": f"Synthesis encountered an error: {str(e)}",
            "pipeline_log": state.get("pipeline_log", []) + [log_entry],
        }


def _generate_fallback_followups(intent: str, state: InsightState) -> list:
    """Generate follow-up question suggestions without LLM."""
    filename = state.get("dataset_filename", "the data")
    numeric_cols = state.get("data_slice", {}).get("numeric_columns", [])
    
    suggestions = {
        "trend_analysis": [
            "Are there any anomalies in the data?",
            f"What drives the changes in {numeric_cols[0] if numeric_cols else 'the main metric'}?",
            "How do different categories compare?",
        ],
        "comparison": [
            "What's the overall trend over time?",
            "Are there any outliers in the data?",
            "What correlations exist between the columns?",
        ],
        "anomaly_detection": [
            "What's causing these anomalies?",
            "What's the overall trend?",
            "How do the groups compare?",
        ],
        "correlation": [
            "What's the trend over time?",
            "Are there any anomalies?",
            "Give me a summary of the data",
        ],
        "causal_analysis": [
            "What correlations exist?",
            "Are there any anomalies?",
            "Compare the different categories",
        ],
    }
    
    return suggestions.get(intent, [
        "What are the main trends?",
        "Are there any anomalies?",
        "How do the categories compare?",
    ])
