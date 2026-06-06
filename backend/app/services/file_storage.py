"""
FILE STORAGE SERVICE — Save & Load Uploaded CSVs
=================================================
In Week 1, we analyzed CSVs on-the-fly and discarded them.
Now we need to KEEP them so the query pipeline can access them later.

WHY STORE FILES?
  When the user asks "Why are sales dropping?", we need to:
  1. Load the previously uploaded CSV
  2. Filter it based on the query
  3. Run statistical tests
  
  Without stored files, the user would need to re-upload for every question.

STORAGE STRATEGY:
  - Files saved to: backend/data/uploads/
  - Filename: original name (sanitized for safety)
  - Also keep a DataFrame cache in memory for fast access
"""

import pandas as pd
import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Storage directory
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "uploads"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory cache of loaded DataFrames
# Key: filename, Value: DataFrame
_df_cache: dict[str, pd.DataFrame] = {}


def sanitize_filename(filename: str) -> str:
    """
    Remove potentially dangerous characters from filenames.
    
    WHY SANITIZE?
    A malicious filename like "../../../etc/passwd" could escape the
    upload directory. We strip everything except letters, numbers,
    underscores, hyphens, and dots.
    """
    # Keep only safe characters
    safe = re.sub(r'[^\w\-.]', '_', filename)
    # Prevent directory traversal
    safe = safe.replace('..', '_')
    return safe


def save_uploaded_file(filename: str, content: bytes) -> str:
    """
    Save an uploaded CSV file to disk and cache the DataFrame.
    
    Args:
        filename: Original filename from the upload
        content: Raw file bytes
    
    Returns:
        The sanitized filename (use this to reference the file later)
    """
    safe_name = sanitize_filename(filename)
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    
    with open(filepath, 'wb') as f:
        f.write(content)
    
    logger.info(f"Saved uploaded file: {safe_name} ({len(content)} bytes)")
    
    # Also cache the DataFrame
    try:
        import io
        df = pd.read_csv(io.BytesIO(content))
        _df_cache[safe_name] = df
        logger.info(f"Cached DataFrame for {safe_name}: {len(df)} rows × {len(df.columns)} cols")
    except Exception as e:
        logger.warning(f"Could not cache DataFrame for {safe_name}: {e}")
    
    return safe_name


def load_dataframe(filename: str) -> Optional[pd.DataFrame]:
    """
    Load a DataFrame from cache or disk.
    
    Checks cache first (fast), falls back to disk read (slower).
    
    Args:
        filename: The sanitized filename
    
    Returns:
        DataFrame or None if file not found
    """
    safe_name = sanitize_filename(filename)
    
    # Check cache first
    if safe_name in _df_cache:
        logger.info(f"Loaded {safe_name} from cache")
        return _df_cache[safe_name]
    
    # Try loading from disk
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            _df_cache[safe_name] = df  # Cache for next time
            logger.info(f"Loaded {safe_name} from disk: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Failed to load {safe_name}: {e}")
            return None
    
    logger.warning(f"File not found: {safe_name}")
    return None


def get_available_files() -> list[str]:
    """List all uploaded CSV files."""
    if not os.path.exists(UPLOAD_DIR):
        return []
    return [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.csv')]
