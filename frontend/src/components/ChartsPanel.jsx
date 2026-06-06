/**
 * CHARTS PANEL — Visualizations Display
 * ======================================
 * Renders both:
 *   1. Server-generated charts (base64 images from matplotlib)
 *   2. Interactive Recharts charts (built from distribution data)
 * 
 * WHY TWO TYPES OF CHARTS?
 *   - Matplotlib charts (heatmaps, KDE plots): Statistically richer,
 *     better for complex visualizations. But they're static images.
 *   - Recharts (bar charts, line charts): Interactive — users can
 *     hover to see values, zoom, and explore. Better UX.
 *   
 *   Using both gives us the best of both worlds.
 * 
 * RECHARTS CONCEPTS:
 *   - ResponsiveContainer: Auto-sizes the chart to its parent
 *   - BarChart/LineChart: The chart type
 *   - XAxis/YAxis: Axis configuration
 *   - Tooltip: Hover popup showing data values
 *   - Bar/Line: The actual data visualization element
 */
"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { BarChart3, Image, ChevronDown, ChevronUp } from "lucide-react";

export default function ChartsPanel({ data }) {
  const [activeTab, setActiveTab] = useState("interactive");
  const [selectedCol, setSelectedCol] = useState(null);

  if (!data) return null;

  const { charts, distributions, numeric_columns } = data;
  const hasCharts = charts && Object.keys(charts).length > 0;
  const hasDistributions = distributions && Object.keys(distributions).length > 0;

  // Default to first numeric column for interactive charts
  const displayCol = selectedCol || (numeric_columns?.[0]);

  return (
    <div className="space-y-5 animate-slide-up">
      {/* ─── Tab Switcher ─── */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab("interactive")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
            ${activeTab === "interactive"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] border border-transparent"
            }`}
        >
          <BarChart3 className="w-4 h-4" />
          Interactive Charts
        </button>
        <button
          onClick={() => setActiveTab("static")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
            ${activeTab === "static"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] border border-transparent"
            }`}
        >
          <Image className="w-4 h-4" />
          Statistical Charts
        </button>
      </div>

      {/* ─── Interactive Charts (Recharts) ─── */}
      {activeTab === "interactive" && (
        <div className="space-y-4">
          {hasDistributions ? (
            <>
              {/* Column selector */}
              <div className="flex flex-wrap gap-2">
                {numeric_columns?.slice(0, 10).map((col) => (
                  <button
                    key={col}
                    onClick={() => setSelectedCol(col)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                      ${displayCol === col
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : "bg-[var(--surface-secondary)] text-[var(--text-tertiary)] border border-[var(--border-primary)] hover:text-[var(--text-secondary)]"
                      }`}
                  >
                    {col}
                  </button>
                ))}
              </div>

              {/* Distribution chart */}
              {displayCol && distributions[displayCol] && (
                <div className="glass-card p-5">
                  <h4 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
                    Distribution of <span className="text-emerald-400">{displayCol}</span>
                  </h4>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={distributions[displayCol]} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                      <XAxis
                        dataKey="range"
                        tick={{ fill: "var(--text-tertiary)", fontSize: 10 }}
                        angle={-45}
                        textAnchor="end"
                        height={80}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                        label={{ value: "Count", angle: -90, position: "insideLeft", fill: "var(--text-tertiary)", fontSize: 11 }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--surface-secondary)",
                          border: "1px solid var(--border-primary)",
                          borderRadius: "8px",
                          color: "var(--text-primary)",
                          fontSize: "12px",
                        }}
                        labelStyle={{ color: "var(--text-secondary)" }}
                        cursor={{ fill: "rgba(16, 185, 129, 0.05)" }}
                      />
                      <Bar
                        dataKey="count"
                        fill="#10b981"
                        radius={[4, 4, 0, 0]}
                        fillOpacity={0.8}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          ) : (
            <EmptyState message="No numeric columns found for interactive charts" />
          )}
        </div>
      )}

      {/* ─── Static Charts (matplotlib base64 images) ─── */}
      {activeTab === "static" && (
        <div className="space-y-4">
          {hasCharts ? (
            Object.entries(charts).map(([name, base64]) => (
              <ChartImage key={name} name={name} base64={base64} />
            ))
          ) : (
            <EmptyState message="No statistical charts were generated" />
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Static Chart Image Sub-Component ─── */
function ChartImage({ name, base64 }) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Format chart name: "correlation_heatmap" → "Correlation Heatmap"
  const displayName = name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-[var(--surface-secondary)] transition-colors"
      >
        <h4 className="text-sm font-semibold text-[var(--text-primary)]">
          {displayName}
        </h4>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-[var(--text-tertiary)]" />
        ) : (
          <ChevronDown className="w-4 h-4 text-[var(--text-tertiary)]" />
        )}
      </button>
      {isExpanded && (
        <div className="px-4 pb-4">
          <img
            src={`data:image/png;base64,${base64}`}
            alt={displayName}
            className="w-full rounded-lg"
            loading="lazy"
          />
        </div>
      )}
    </div>
  );
}

/* ─── Empty State ─── */
function EmptyState({ message }) {
  return (
    <div className="text-center py-12 text-[var(--text-tertiary)]">
      <BarChart3 className="w-10 h-10 mx-auto mb-2 opacity-40" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
