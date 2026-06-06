/**
 * STATS PANEL — Dataset Overview & Column Statistics
 * ===================================================
 * Displays the high-level dataset info (rows, columns, memory)
 * and per-column statistics in a sortable table.
 * 
 * REACT CONCEPTS:
 *   - Conditional rendering with ternary: condition ? <A/> : <B/>
 *   - Array.map() to render lists of items
 *   - Computed values from props (no separate state needed)
 */
"use client";

import { useState } from "react";
import { Rows3, Columns3, HardDrive, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";

export default function StatsPanel({ data }) {
  const [expandedCol, setExpandedCol] = useState(null);

  if (!data) return null;

  const { row_count, column_count, memory_usage_mb, columns, numeric_columns, categorical_columns, datetime_columns } = data;

  return (
    <div className="space-y-6 animate-slide-up">
      {/* ─── Overview Cards ─── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          icon={<Rows3 className="w-4 h-4" />}
          label="Rows"
          value={row_count?.toLocaleString()}
          color="emerald"
        />
        <StatCard
          icon={<Columns3 className="w-4 h-4" />}
          label="Columns"
          value={column_count}
          color="blue"
        />
        <StatCard
          icon={<HardDrive className="w-4 h-4" />}
          label="Memory"
          value={`${memory_usage_mb} MB`}
          color="purple"
        />
        <StatCard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Missing Cells"
          value={columns?.reduce((sum, c) => sum + c.missing_count, 0)?.toLocaleString()}
          color="amber"
        />
      </div>

      {/* ─── Column Type Breakdown ─── */}
      <div className="flex flex-wrap gap-2">
        {numeric_columns?.length > 0 && (
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            {numeric_columns.length} Numeric
          </span>
        )}
        {categorical_columns?.length > 0 && (
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
            {categorical_columns.length} Categorical
          </span>
        )}
        {datetime_columns?.length > 0 && (
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
            {datetime_columns.length} Datetime
          </span>
        )}
      </div>

      {/* ─── Column Details Table ─── */}
      <div className="rounded-xl border border-[var(--border-primary)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--surface-secondary)] text-[var(--text-secondary)]">
                <th className="text-left px-4 py-3 font-medium">Column</th>
                <th className="text-left px-4 py-3 font-medium">Type</th>
                <th className="text-right px-4 py-3 font-medium">Missing %</th>
                <th className="text-right px-4 py-3 font-medium">Unique</th>
                <th className="text-right px-4 py-3 font-medium hidden md:table-cell">Mean</th>
                <th className="text-right px-4 py-3 font-medium hidden md:table-cell">Median</th>
                <th className="text-right px-4 py-3 font-medium hidden lg:table-cell">Std</th>
                <th className="text-center px-4 py-3 font-medium w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-secondary)]">
              {columns?.map((col, idx) => (
                <ColumnRow 
                  key={col.name} 
                  col={col} 
                  idx={idx}
                  isExpanded={expandedCol === col.name}
                  onToggle={() => setExpandedCol(expandedCol === col.name ? null : col.name)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ─── Stat Card Sub-Component ─── */
function StatCard({ icon, label, value, color }) {
  const colorMap = {
    emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    amber: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  };

  return (
    <div className="glass-card glow-hover p-4">
      <div className={`inline-flex p-2 rounded-lg border ${colorMap[color]} mb-2`}>
        {icon}
      </div>
      <p className="text-2xl font-bold text-[var(--text-primary)]">{value}</p>
      <p className="text-xs text-[var(--text-tertiary)] mt-0.5">{label}</p>
    </div>
  );
}

/* ─── Column Row Sub-Component ─── */
function ColumnRow({ col, idx, isExpanded, onToggle }) {
  const typeColors = {
    numeric: "text-emerald-400 bg-emerald-500/10",
    categorical: "text-blue-400 bg-blue-500/10",
    datetime: "text-purple-400 bg-purple-500/10",
    boolean: "text-amber-400 bg-amber-500/10",
  };

  // Missing % color coding
  const getMissingColor = (pct) => {
    if (pct > 40) return "text-red-400";
    if (pct > 20) return "text-amber-400";
    if (pct > 5) return "text-yellow-400";
    return "text-[var(--text-secondary)]";
  };

  return (
    <>
      <tr 
        className="hover:bg-[var(--surface-secondary)] transition-colors cursor-pointer"
        onClick={onToggle}
        style={{ animationDelay: `${idx * 30}ms` }}
      >
        <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
          {col.name}
        </td>
        <td className="px-4 py-3">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[col.dtype] || "text-gray-400 bg-gray-500/10"}`}>
            {col.dtype}
          </span>
        </td>
        <td className={`px-4 py-3 text-right font-mono text-xs ${getMissingColor(col.missing_pct)}`}>
          {col.missing_pct > 0 ? `${col.missing_pct}%` : "—"}
        </td>
        <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs">
          {col.unique_count?.toLocaleString()}
        </td>
        <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs hidden md:table-cell">
          {col.mean != null ? col.mean.toFixed(2) : "—"}
        </td>
        <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs hidden md:table-cell">
          {col.median != null ? col.median.toFixed(2) : "—"}
        </td>
        <td className="px-4 py-3 text-right text-[var(--text-secondary)] font-mono text-xs hidden lg:table-cell">
          {col.std != null ? col.std.toFixed(2) : "—"}
        </td>
        <td className="px-4 py-3 text-center">
          {isExpanded 
            ? <ChevronUp className="w-4 h-4 text-[var(--text-tertiary)]" />
            : <ChevronDown className="w-4 h-4 text-[var(--text-tertiary)]" />
          }
        </td>
      </tr>
      
      {/* Expanded details row */}
      {isExpanded && (
        <tr className="bg-[var(--surface-secondary)]">
          <td colSpan={8} className="px-4 py-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
              {col.dtype === "numeric" && (
                <>
                  <div>
                    <span className="text-[var(--text-tertiary)]">Min:</span>{" "}
                    <span className="text-[var(--text-primary)] font-mono">{col.min_val?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-tertiary)]">Max:</span>{" "}
                    <span className="text-[var(--text-primary)] font-mono">{col.max_val?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-tertiary)]">Skewness:</span>{" "}
                    <span className={`font-mono ${col.skewness && Math.abs(col.skewness) > 1.5 ? "text-amber-400" : "text-[var(--text-primary)]"}`}>
                      {col.skewness?.toFixed(3) ?? "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-tertiary)]">Missing:</span>{" "}
                    <span className="text-[var(--text-primary)] font-mono">{col.missing_count} / {col.total_count}</span>
                  </div>
                </>
              )}
              {col.dtype === "categorical" && col.top_values && (
                <div className="col-span-full">
                  <span className="text-[var(--text-tertiary)] block mb-1">Top Values:</span>
                  <div className="flex flex-wrap gap-2">
                    {col.top_values.map((v, i) => (
                      <span key={i} className="px-2 py-1 rounded bg-[var(--surface-tertiary)] text-[var(--text-secondary)] font-mono">
                        {v.value} <span className="text-[var(--text-muted)]">({v.count})</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
