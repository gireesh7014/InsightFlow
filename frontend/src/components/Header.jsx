/**
 * HEADER COMPONENT
 * ================
 * The app's top navigation bar with branding and status indicators.
 * 
 * REACT CONCEPTS USED:
 *   - Props: Data passed from parent to child component
 *   - Conditional rendering: {condition && <element>}
 *   - Template literals: `${variable}` for dynamic strings
 */
"use client"; // This tells Next.js this component runs in the browser

import { Activity, Database, Clock } from "lucide-react";

/**
 * @param {Object} props
 * @param {boolean} props.isConnected - Whether the backend is reachable
 * @param {number} props.uploadCount - Number of analyses performed this session
 */
export default function Header({ isConnected, uploadCount = 0 }) {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border-primary)] bg-[var(--surface-primary)]/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* ─── Logo & Brand ─── */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-[var(--text-primary)] tracking-tight">
                InsightFlow
              </h1>
              <p className="text-[11px] text-[var(--text-tertiary)] -mt-0.5">
                Decision Intelligence System
              </p>
            </div>
          </div>

          {/* ─── Right side indicators ─── */}
          <div className="flex items-center gap-4">
            {/* Analysis count */}
            {uploadCount > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
                <Database className="w-3.5 h-3.5" />
                <span>{uploadCount} analysis{uploadCount !== 1 ? "es" : ""}</span>
              </div>
            )}

            {/* Backend status indicator */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface-secondary)] border border-[var(--border-primary)]">
              <div
                className={`w-2 h-2 rounded-full ${
                  isConnected
                    ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]"
                    : "bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.5)]"
                }`}
              />
              <span className="text-xs text-[var(--text-secondary)]">
                {isConnected ? "API Connected" : "API Offline"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
