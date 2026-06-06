/**
 * MAIN PAGE — InsightFlow Landing & Analysis Page
 * =================================================
 * This is the main (and only) page of our app. It orchestrates:
 *   1. File upload
 *   2. API call to backend
 *   3. Display results in tabs (Stats → Insights → Charts)
 * 
 * REACT STATE MANAGEMENT CONCEPTS:
 *   We use multiple useState hooks to manage different pieces of state:
 *   - analysisData: The response from the backend (null until upload)
 *   - isLoading: Whether we're waiting for the backend
 *   - error: Any error message to display
 *   - activeTab: Which results tab is selected
 *   - uploadCount: How many analyses this session
 * 
 *   WHY NOT useReducer OR A STATE LIBRARY?
 *   For our app, useState is sufficient. You'd switch to useReducer
 *   when state transitions get complex (e.g., loading → success AND
 *   loading → error AND success → re-upload). For now, KISS.
 * 
 * "use client":
 *   Next.js 13+ defaults to Server Components (rendered on the server).
 *   We need "use client" because we use useState, useEffect, and event
 *   handlers — these only work in the browser.
 */
"use client";

import { useState, useEffect, useCallback } from "react";
import Header from "@/components/Header";
import FileUpload from "@/components/FileUpload";
import StatsPanel from "@/components/StatsPanel";
import InsightsPanel from "@/components/InsightsPanel";
import ChartsPanel from "@/components/ChartsPanel";
import QueryPanel from "@/components/QueryPanel";
import { analyzeCSV, checkHealth } from "@/lib/api";
import {
  BarChart3,
  Lightbulb,
  Table2,
  Sparkles,
  ArrowRight,
  Zap,
  Shield,
  Brain,
  MessageSquare,
} from "lucide-react";

export default function Home() {
  // ─── State ─────────────────────────────────────────────
  const [analysisData, setAnalysisData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("insights");
  const [isConnected, setIsConnected] = useState(false);
  const [uploadCount, setUploadCount] = useState(0);
  const [uploadedFilename, setUploadedFilename] = useState(null);

  // ─── Check backend connection on mount ─────────────────
  useEffect(() => {
    const check = async () => {
      const healthy = await checkHealth();
      setIsConnected(healthy);
    };
    check();
    // Re-check every 30 seconds
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  // ─── Handle file upload & analysis ─────────────────────
  const handleFileSelect = useCallback(async (file) => {
    setIsLoading(true);
    setError(null);
    setAnalysisData(null);

    try {
      const data = await analyzeCSV(file);
      setAnalysisData(data);
      setUploadedFilename(file.name);  // Track filename for queries
      setUploadCount((prev) => prev + 1);
      setActiveTab("insights"); // Start with insights tab
    } catch (err) {
      setError(err.message || "Analysis failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ─── Tab configuration ─────────────────────────────────
  const tabs = [
    {
      id: "insights",
      label: "Insights",
      icon: <Lightbulb className="w-4 h-4" />,
      count: analysisData?.insights?.length,
    },
    {
      id: "stats",
      label: "Statistics",
      icon: <Table2 className="w-4 h-4" />,
      count: analysisData?.column_count,
    },
    {
      id: "charts",
      label: "Visualizations",
      icon: <BarChart3 className="w-4 h-4" />,
      count: analysisData?.charts
        ? Object.keys(analysisData.charts).length
        : 0,
    },
    {
      id: "ask",
      label: "Ask Questions",
      icon: <MessageSquare className="w-4 h-4" />,
      count: null,  // No count badge for this tab
    },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Header isConnected={isConnected} uploadCount={uploadCount} />

      {/* ─── Background Glow Effect ─── */}
      <div className="fixed inset-0 pointer-events-none" style={{ background: "var(--gradient-glow)" }} />

      <main className="flex-1 relative">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

          {/* ─── Hero Section (shown before upload) ─── */}
          {!analysisData && !isLoading && (
            <div className="text-center mb-10 animate-fade-in">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium mb-6">
                <Sparkles className="w-3.5 h-3.5" />
                Decision Intelligence System
              </div>
              <h2 className="text-4xl sm:text-5xl font-bold text-[var(--text-primary)] tracking-tight mb-4">
                Turn raw data into
                <span className="gradient-text"> actionable insights</span>
              </h2>
              <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto mb-8">
                Upload any CSV file and get instant statistical analysis, ranked data quality 
                insights, and auto-generated visualizations — no configuration needed.
              </p>

              {/* Feature cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl mx-auto mb-10">
                <FeatureCard
                  icon={<Zap className="w-5 h-5 text-emerald-400" />}
                  title="20 Insight Rules"
                  desc="Automatic data quality checks, correlation detection, and anomaly flagging"
                />
                <FeatureCard
                  icon={<BarChart3 className="w-5 h-5 text-blue-400" />}
                  title="Auto Visualizations"
                  desc="Correlation heatmaps, distributions, box plots — generated automatically"
                />
                <FeatureCard
                  icon={<Shield className="w-5 h-5 text-purple-400" />}
                  title="Ranked Severity"
                  desc="Critical → Warning → Info — know what matters most at a glance"
                />
              </div>
            </div>
          )}

          {/* ─── File Upload Zone ─── */}
          <div className="mb-8">
            <FileUpload onFileSelect={handleFileSelect} isLoading={isLoading} />
          </div>

          {/* ─── Error Display ─── */}
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/5 border border-red-500/20 animate-slide-up">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
                  <span className="text-red-400 text-lg">!</span>
                </div>
                <div>
                  <p className="font-medium text-red-400 text-sm">Analysis Failed</p>
                  <p className="text-sm text-red-300/80 mt-1">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* ─── Results Section ─── */}
          {analysisData && (
            <div className="animate-slide-up">
              {/* Tab Navigation */}
              <div className="flex items-center gap-1 mb-6 p-1 rounded-xl bg-[var(--surface-primary)] border border-[var(--border-primary)] w-fit">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all
                      ${activeTab === tab.id
                        ? "bg-emerald-500/15 text-emerald-400 shadow-sm"
                        : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--surface-secondary)]"
                      }`}
                  >
                    {tab.icon}
                    {tab.label}
                    {tab.count > 0 && (
                      <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold
                        ${activeTab === tab.id
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-[var(--surface-tertiary)] text-[var(--text-muted)]"
                        }`}>
                        {tab.count}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="min-h-[400px]">
                {activeTab === "insights" && <InsightsPanel data={analysisData} />}
                {activeTab === "stats" && <StatsPanel data={analysisData} />}
                {activeTab === "charts" && <ChartsPanel data={analysisData} />}
                {activeTab === "ask" && <QueryPanel filename={uploadedFilename} />}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ─── Footer ─── */}
      <footer className="border-t border-[var(--border-primary)] py-4 mt-auto">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p className="text-xs text-[var(--text-muted)]">
            InsightFlow v2.0 — Decision Intelligence System · Built with FastAPI + Next.js + LangGraph + Gemini
          </p>
        </div>
      </footer>
    </div>
  );
}

/* ─── Feature Card (Hero Section) ─── */
function FeatureCard({ icon, title, desc }) {
  return (
    <div className="glass-card glow-hover p-5 text-left">
      <div className="mb-3">{icon}</div>
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">{title}</h3>
      <p className="text-xs text-[var(--text-tertiary)] leading-relaxed">{desc}</p>
    </div>
  );
}
