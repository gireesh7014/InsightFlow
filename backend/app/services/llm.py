"""
LLM SERVICE — Google Gemini Integration
========================================
Centralizes all LLM (Large Language Model) interactions in one place.

WHY A SEPARATE LLM SERVICE?
  1. Single place to swap LLM providers (Gemini → OpenAI → Anthropic)
  2. Consistent error handling for rate limits, API failures
  3. Structured output parsing in one place
  4. Token/cost monitoring

GOOGLE GEMINI FREE TIER:
  - Model: gemini-2.0-flash (fast, capable, FREE)
  - Rate limit: 15 requests per minute
  - No credit card required
  - Get your key at: https://aistudio.google.com/apikey

HOW LLMs WORK (simplified):
  1. You send a "prompt" (text) to the API
  2. The model generates a "completion" (response text)
  3. The "system prompt" sets the model's persona/rules
  4. "Temperature" controls randomness:
     - 0.0 = deterministic (always same answer) — good for analysis
     - 1.0 = creative (varied answers) — good for writing
"""

import google.generativeai as genai
import json
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# ─── Initialize Gemini ─────────────────────────────────────
_api_key = os.getenv("GOOGLE_API_KEY", "")
_model = None


def _get_model():
    """
    Lazy initialization of the Gemini model.
    
    WHY LAZY?
    We don't want the app to crash on startup if the API key is missing.
    Instead, we initialize the model on first use and give a clear error.
    """
    global _model
    if _model is not None:
        return _model
    
    if not _api_key or _api_key == "your_gemini_api_key_here":
        logger.warning("GOOGLE_API_KEY not set — LLM features will use fallback mode")
        return None
    
    try:
        genai.configure(api_key=_api_key)
        _model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.1,       # Low temp = deterministic, factual
                "top_p": 0.95,
                "max_output_tokens": 2048,
            }
        )
        logger.info("Gemini model initialized successfully (gemini-2.0-flash)")
        return _model
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        return None


def is_llm_available() -> bool:
    """Check if the LLM is configured and available."""
    return _get_model() is not None


async def generate_structured_output(prompt: str, system_prompt: str = "") -> dict:
    """
    Ask Gemini to return a structured JSON response.
    
    STRUCTURED OUTPUT:
    Instead of free-form text, we ask the LLM to return JSON with specific fields.
    This makes the output predictable and parseable by code.
    
    Example prompt: "Classify this query. Return JSON with fields: intent, columns, confidence"
    Example output: {"intent": "trend_analysis", "columns": ["sales"], "confidence": 0.85}
    
    Args:
        prompt: The question/instruction for the LLM
        system_prompt: Sets the model's behavior rules
    
    Returns:
        Parsed dict from JSON response, or empty dict on failure
    """
    model = _get_model()
    if model is None:
        return {}
    
    try:
        full_prompt = ""
        if system_prompt:
            full_prompt += f"System instructions: {system_prompt}\n\n"
        full_prompt += prompt
        full_prompt += "\n\nRespond with valid JSON only. No markdown, no explanation."
        
        response = model.generate_content(full_prompt)
        text = response.text.strip()
        
        # Clean up markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
        
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return {}


async def generate_text(prompt: str, system_prompt: str = "") -> str:
    """
    Ask Gemini for a free-form text response.
    
    Used in Node 4 (Synthesis) where we want a natural-language explanation,
    not structured data.
    
    Args:
        prompt: The question/instruction
        system_prompt: Sets behavior rules
    
    Returns:
        Generated text string, or fallback message on failure
    """
    model = _get_model()
    if model is None:
        return _fallback_text_response(prompt)
    
    try:
        full_prompt = ""
        if system_prompt:
            full_prompt += f"System instructions: {system_prompt}\n\n"
        full_prompt += prompt
        
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"LLM text generation failed: {e}")
        return _fallback_text_response(prompt)


def _fallback_text_response(prompt: str) -> str:
    """
    Provide a basic response when the LLM is unavailable.
    
    This ensures the system degrades gracefully — users still get
    useful information even without the LLM.
    """
    return (
        "Analysis complete. The statistical results are shown above. "
        "For a detailed natural-language explanation, please configure "
        "your Google Gemini API key in the .env file."
    )
