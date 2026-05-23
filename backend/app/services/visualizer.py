"""
VISUALIZATION ENGINE — Server-Side Chart Generation
====================================================
Generates matplotlib/seaborn charts and encodes them as base64 strings
that can be embedded directly in JSON API responses.

WHY SERVER-SIDE CHARTS?
  Statistical plots (heatmaps, distribution plots with KDE curves)
  look much better in matplotlib/seaborn than in JavaScript charting
  libraries. We generate these on the backend and send them as images.
  
  For interactive charts (where users hover, zoom, filter), we send
  raw data to the frontend and use Recharts (a React charting library).

HOW BASE64 ENCODING WORKS:
  1. matplotlib renders a chart → saves to a BytesIO buffer (in-memory file)
  2. We read the raw bytes from the buffer
  3. base64.b64encode() converts bytes to a text string
  4. The frontend displays it: <img src="data:image/png;base64,{string}" />
  
  This avoids saving files to disk or serving static images.

MATPLOTLIB CONCEPTS:
  - Figure: The entire image canvas
  - Axes: A single plot within the figure
  - fig, ax = plt.subplots(): Creates a figure with one plot
  - fig, axes = plt.subplots(2, 3): Creates a 2×3 grid of plots
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend (no GUI window needed on server)

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import base64
import io
import logging

logger = logging.getLogger(__name__)

# ─── Style Configuration ──────────────────────────────────────
# Set a clean, modern style for all charts
sns.set_theme(style="darkgrid", palette="viridis")
plt.rcParams.update({
    'figure.facecolor': '#0f1117',    # Dark background
    'axes.facecolor': '#1a1d29',      # Dark plot area
    'text.color': '#e0e0e0',          # Light text
    'axes.labelcolor': '#e0e0e0',
    'xtick.color': '#a0a0a0',
    'ytick.color': '#a0a0a0',
    'grid.color': '#2a2d3a',
    'grid.alpha': 0.5,
    'font.size': 10,
    'axes.titlesize': 13,
    'axes.labelsize': 11,
})


def _fig_to_base64(fig: plt.Figure) -> str:
    """
    Convert a matplotlib figure to a base64-encoded PNG string.
    
    This is the bridge between Python's plotting world and the web.
    The frontend receives this string and displays it as:
      <img src="data:image/png;base64,{this_string}" />
    """
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buffer.seek(0)
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close(fig)
    buffer.close()
    return img_str


def generate_correlation_heatmap(df: pd.DataFrame, numeric_cols: list) -> str:
    """
    Generate a correlation heatmap using seaborn.
    
    WHAT IS A CORRELATION HEATMAP?
    A color-coded matrix showing correlation between every pair of
    numeric columns. Red/warm = positive correlation, Blue/cool = negative.
    
    HOW TO READ IT:
    - Each cell shows the Pearson r value
    - Diagonal is always 1.0 (column correlated with itself)
    - Symmetric: correlation(A,B) = correlation(B,A)
    - Look for clusters of high values = related feature groups
    """
    if len(numeric_cols) < 2:
        return None
    
    try:
        # Limit to 15 columns for readability
        cols = numeric_cols[:15]
        corr_matrix = df[cols].corr()
        
        fig_size = max(8, len(cols) * 0.8)
        fig, ax = plt.subplots(figsize=(fig_size, fig_size))
        
        # Create heatmap
        # annot=True shows the r value in each cell
        # fmt=".2f" formats to 2 decimal places
        # cmap="RdYlBu_r" = Red (positive) → Yellow (zero) → Blue (negative)
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)  # Show only lower triangle
        sns.heatmap(
            corr_matrix,
            mask=mask,
            annot=True,
            fmt=".2f",
            cmap="RdYlBu_r",
            center=0,
            vmin=-1, vmax=1,
            square=True,
            linewidths=0.5,
            linecolor='#2a2d3a',
            cbar_kws={"shrink": 0.8, "label": "Correlation (r)"},
            ax=ax,
            annot_kws={"size": 9}
        )
        
        ax.set_title("Correlation Matrix", fontsize=14, fontweight='bold', pad=15)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        fig.tight_layout()
        
        return _fig_to_base64(fig)
    except Exception as e:
        logger.error(f"Failed to generate correlation heatmap: {e}")
        return None


def generate_missing_values_chart(df: pd.DataFrame) -> str:
    """
    Generate a bar chart showing missing value percentages per column.
    
    WHY VISUALIZE MISSING DATA?
    Numbers alone don't convey the pattern. A heatmap can reveal:
    - Random missing: scattered everywhere (usually okay to impute)
    - Structural missing: entire sections missing (data collection issue)
    - Correlated missing: when col A is missing, col B is too (important!)
    """
    try:
        missing = df.isnull().sum()
        missing_pct = (missing / len(df)) * 100
        
        # Only show columns with missing values
        missing_pct = missing_pct[missing_pct > 0].sort_values(ascending=True)
        
        if len(missing_pct) == 0:
            return None
        
        fig, ax = plt.subplots(figsize=(10, max(4, len(missing_pct) * 0.4)))
        
        # Color bars by severity
        colors = []
        for pct in missing_pct.values:
            if pct > 40:
                colors.append('#ef4444')     # Red — critical
            elif pct > 20:
                colors.append('#f59e0b')     # Amber — warning
            else:
                colors.append('#22c55e')     # Green — info
        
        bars = ax.barh(range(len(missing_pct)), missing_pct.values, color=colors, height=0.6)
        ax.set_yticks(range(len(missing_pct)))
        ax.set_yticklabels(missing_pct.index)
        ax.set_xlabel('Missing Values (%)')
        ax.set_title('Missing Values by Column', fontsize=14, fontweight='bold', pad=15)
        
        # Add percentage labels on bars
        for bar, pct in zip(bars, missing_pct.values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{pct:.1f}%', va='center', fontsize=9, color='#e0e0e0')
        
        ax.set_xlim(0, min(100, missing_pct.max() * 1.15))
        fig.tight_layout()
        
        return _fig_to_base64(fig)
    except Exception as e:
        logger.error(f"Failed to generate missing values chart: {e}")
        return None


def generate_distribution_plots(df: pd.DataFrame, numeric_cols: list) -> str:
    """
    Generate distribution plots (histogram + KDE) for numeric columns.
    
    WHAT IS KDE (Kernel Density Estimation)?
    A smooth curve approximating the histogram. Think of it as a 
    "smoothed histogram" that shows the probability density.
    
    WHY BOTH HISTOGRAM AND KDE?
    - Histogram: Shows actual counts, but shape depends on bin width
    - KDE: Shows the underlying shape, independent of binning
    - Together: Best of both worlds
    """
    cols = numeric_cols[:9]  # Limit to 9 for a 3×3 grid
    if not cols:
        return None
    
    try:
        n_cols = len(cols)
        n_rows = (n_cols + 2) // 3  # Ceiling division for 3 columns
        
        fig, axes = plt.subplots(n_rows, 3, figsize=(14, 4 * n_rows))
        if n_rows == 1:
            axes = axes.reshape(1, -1)
        axes = axes.flatten()
        
        for idx, col in enumerate(cols):
            ax = axes[idx]
            data = df[col].dropna()
            
            if len(data) < 2:
                ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center',
                        transform=ax.transAxes, color='#a0a0a0')
                ax.set_title(col, fontsize=11)
                continue
            
            # Plot histogram with KDE
            sns.histplot(data, kde=True, ax=ax, color='#6366f1', edgecolor='#4338ca',
                         alpha=0.7, linewidth=0.5)
            
            # Add mean and median lines
            mean_val = data.mean()
            median_val = data.median()
            ax.axvline(mean_val, color='#ef4444', linestyle='--', linewidth=1.5, label=f'Mean: {mean_val:.1f}')
            ax.axvline(median_val, color='#22c55e', linestyle='--', linewidth=1.5, label=f'Median: {median_val:.1f}')
            
            ax.legend(fontsize=8, loc='upper right')
            ax.set_title(col, fontsize=11, fontweight='bold')
            ax.set_xlabel('')
            ax.set_ylabel('')
        
        # Hide unused subplots
        for idx in range(len(cols), len(axes)):
            axes[idx].set_visible(False)
        
        fig.suptitle('Numeric Distributions', fontsize=14, fontweight='bold', y=1.02)
        fig.tight_layout()
        
        return _fig_to_base64(fig)
    except Exception as e:
        logger.error(f"Failed to generate distribution plots: {e}")
        return None


def generate_box_plots(df: pd.DataFrame, numeric_cols: list) -> str:
    """
    Generate box plots for outlier visualization.
    
    HOW TO READ A BOX PLOT:
    ┌─────────┐
    │   ┬      │  ← Maximum (or upper whisker = Q3 + 1.5×IQR)
    │   │      │
    │ ┌─┤─┐    │  ← Q3 (75th percentile)
    │ │ │ │    │
    │ │ ├─│    │  ← Median (50th percentile) — the line in the box
    │ │ │ │    │
    │ └─┤─┘    │  ← Q1 (25th percentile)
    │   │      │
    │   ┴      │  ← Minimum (or lower whisker = Q1 - 1.5×IQR)
    │   •      │  ← Outlier (beyond whiskers)
    └─────────┘
    
    IQR (Interquartile Range) = Q3 - Q1 (the box height)
    Outliers: points beyond Q1 - 1.5×IQR or Q3 + 1.5×IQR
    """
    cols = numeric_cols[:10]
    if not cols:
        return None
    
    try:
        fig, ax = plt.subplots(figsize=(max(10, len(cols) * 1.2), 6))
        
        # Prepare data (drop NaN for each column independently)
        data_to_plot = [df[col].dropna().values for col in cols]
        
        bp = ax.boxplot(data_to_plot, labels=cols, patch_artist=True,
                        flierprops=dict(marker='o', markerfacecolor='#ef4444', 
                                       markersize=4, alpha=0.6),
                        medianprops=dict(color='#22c55e', linewidth=2),
                        whiskerprops=dict(color='#a0a0a0'),
                        capprops=dict(color='#a0a0a0'))
        
        # Color boxes with gradient
        colors = plt.cm.viridis(np.linspace(0.3, 0.8, len(cols)))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.set_title('Box Plots — Outlier Overview', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Value')
        plt.xticks(rotation=45, ha='right')
        fig.tight_layout()
        
        return _fig_to_base64(fig)
    except Exception as e:
        logger.error(f"Failed to generate box plots: {e}")
        return None


def generate_all_charts(df: pd.DataFrame, numeric_cols: list) -> dict:
    """
    Generate all chart types and return as a dict of base64 strings.
    
    This is the main entry point called by the API route.
    Each chart is generated independently — if one fails, the others
    still work (graceful degradation).
    """
    charts = {}
    
    # 1. Correlation heatmap
    logger.info("Generating correlation heatmap...")
    corr_chart = generate_correlation_heatmap(df, numeric_cols)
    if corr_chart:
        charts["correlation_heatmap"] = corr_chart
    
    # 2. Missing values chart
    logger.info("Generating missing values chart...")
    missing_chart = generate_missing_values_chart(df)
    if missing_chart:
        charts["missing_values"] = missing_chart
    
    # 3. Distribution plots
    logger.info("Generating distribution plots...")
    dist_chart = generate_distribution_plots(df, numeric_cols)
    if dist_chart:
        charts["distributions"] = dist_chart
    
    # 4. Box plots
    logger.info("Generating box plots...")
    box_chart = generate_box_plots(df, numeric_cols)
    if box_chart:
        charts["box_plots"] = box_chart
    
    logger.info(f"Generated {len(charts)} charts successfully")
    return charts
