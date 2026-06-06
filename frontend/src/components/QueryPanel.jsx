/**
 * QUERY PANEL — Natural Language Chat Interface
 * ==============================================
 * Allows users to ask questions about their data in plain English.
 * Shows real-time pipeline progress via SSE streaming.
 * 
 * FEATURES:
 *   - Text input with suggested questions
 *   - Streaming pipeline progress (4 node steps)
 *   - Formatted explanation with confidence badge
 *   - Follow-up question buttons
 *   - "Why this answer?" expandable audit trail
 * 
 * REACT CONCEPTS:
 *   - useRef for auto-scrolling to latest message
 *   - useCallback for memoized event handlers
 *   - Conditional rendering for different states
 */
"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  Send,
  Loader2,
  Brain,
  Database,
  BarChart3,
  FileText,
  ChevronDown,
  ChevronUp,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Sparkles,
  Clock,
  MessageSquare,
} from "lucide-react";
import { queryData } from "@/lib/api";

// Node icons and labels for pipeline progress
const NODE_CONFIG = {
  query_understanding: { icon: Brain, label: "Understanding your question", color: "text-purple-400" },
  data_retrieval: { icon: Database, label: "Fetching relevant data", color: "text-blue-400" },
  analysis: { icon: BarChart3, label: "Running statistical analysis", color: "text-emerald-400" },
  synthesis: { icon: FileText, label: "Writing explanation", color: "text-amber-400" },
};

const CONFIDENCE_CONFIG = {
  High: { color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle2 },
  Medium: { color: "text-amber-400 bg-amber-500/10 border-amber-500/20", icon: AlertTriangle },
  Low: { color: "text-red-400 bg-red-500/10 border-red-500/20", icon: XCircle },
};

export default function QueryPanel({ filename }) {
  // ─── State ─────────────────────────────────────────────
  const [messages, setMessages] = useState([]);  // Chat history
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState([]);
  const [showAuditTrail, setShowAuditTrail] = useState(null); // message index
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pipelineSteps]);

  // ─── Suggested Questions ───────────────────────────────
  const suggestedQuestions = [
    "What are the main trends in the data?",
    "Are there any anomalies or outliers?",
    "Which categories perform best?",
    "What correlations exist between columns?",
    "Give me a summary of the dataset",
  ];

  // ─── Handle Query Submission ───────────────────────────
  const handleSubmit = useCallback(async (query) => {
    if (!query.trim() || isLoading) return;

    const userMessage = {
      type: "user",
      content: query,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);
    setPipelineSteps([]);

    try {
      // Use the synchronous endpoint (simpler, more reliable)
      const response = await queryData(query, filename);

      const assistantMessage = {
        type: "assistant",
        content: response.explanation,
        confidence: response.confidence,
        confidenceReason: response.confidence_reason,
        followUps: response.follow_up_questions || [],
        queryContext: response.query_context,
        analysisResult: response.analysis_result,
        pipelineLog: response.pipeline_log || [],
        dataSummary: response.data_summary,
        elapsed: response.elapsed_s,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage = {
        type: "error",
        content: error.message || "Something went wrong. Please try again.",
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setPipelineSteps([]);
      inputRef.current?.focus();
    }
  }, [filename, isLoading]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(inputValue);
    }
  };

  return (
    <div className="flex flex-col h-[600px] animate-slide-up">
      {/* ─── Chat Messages Area ─── */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
        {/* Empty state */}
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4">
              <MessageSquare className="w-8 h-8 text-emerald-400" />
            </div>
            <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
              Ask anything about your data
            </h3>
            <p className="text-sm text-[var(--text-secondary)] max-w-md mb-6">
              Your question goes through a 4-node pipeline: intent classification →
              data retrieval → statistical analysis → explanation synthesis.
              Every number in the answer comes from actual computation.
            </p>

            {/* Suggested Questions */}
            <div className="flex flex-wrap gap-2 justify-center max-w-xl">
              {suggestedQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSubmit(q)}
                  className="px-3 py-2 rounded-xl text-xs text-[var(--text-secondary)] 
                    bg-[var(--surface-secondary)] border border-[var(--border-primary)]
                    hover:border-[var(--border-accent)] hover:text-emerald-400
                    transition-all duration-200"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Chat Messages */}
        {messages.map((msg, idx) => (
          <div key={idx}>
            {msg.type === "user" && <UserMessage content={msg.content} />}
            {msg.type === "assistant" && (
              <AssistantMessage
                message={msg}
                showAudit={showAuditTrail === idx}
                onToggleAudit={() => setShowAuditTrail(showAuditTrail === idx ? null : idx)}
                onFollowUp={handleSubmit}
              />
            )}
            {msg.type === "error" && <ErrorMessage content={msg.content} />}
          </div>
        ))}

        {/* Loading State */}
        {isLoading && (
          <div className="glass-card p-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" />
              <span className="text-sm text-[var(--text-secondary)]">
                Running pipeline...
              </span>
            </div>
            {/* Pipeline Steps Progress */}
            <div className="mt-3 space-y-2">
              {Object.entries(NODE_CONFIG).map(([key, config]) => {
                const step = pipelineSteps.find(s => s.node === key);
                const Icon = config.icon;
                return (
                  <div key={key} className="flex items-center gap-2 text-xs">
                    <Icon className={`w-3.5 h-3.5 ${step ? config.color : "text-[var(--text-muted)]"}`} />
                    <span className={step ? "text-[var(--text-secondary)]" : "text-[var(--text-muted)]"}>
                      {config.label}
                    </span>
                    {step && (
                      <span className="text-[var(--text-muted)] ml-auto">
                        {step.duration_ms}ms
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ─── Input Area ─── */}
      <div className="flex-shrink-0">
        {/* Quick follow-up suggestions after a response */}
        {messages.length > 0 && !isLoading && messages[messages.length - 1]?.type === "assistant" && (
          <div className="flex flex-wrap gap-2 mb-3">
            {messages[messages.length - 1].followUps?.map((q, i) => (
              <button
                key={i}
                onClick={() => handleSubmit(q)}
                className="px-3 py-1.5 rounded-lg text-xs text-[var(--text-secondary)]
                  bg-[var(--surface-secondary)] border border-[var(--border-primary)]
                  hover:border-[var(--border-accent)] hover:text-emerald-400
                  transition-all"
              >
                ↳ {q}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your data..."
            disabled={isLoading}
            className="flex-1 px-4 py-3 rounded-xl bg-[var(--surface-secondary)] 
              border border-[var(--border-primary)] text-[var(--text-primary)]
              placeholder:text-[var(--text-muted)] text-sm
              focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20
              disabled:opacity-50 transition-all"
            id="query-input"
          />
          <button
            onClick={() => handleSubmit(inputValue)}
            disabled={isLoading || !inputValue.trim()}
            className="px-4 py-3 rounded-xl bg-emerald-500/15 text-emerald-400
              border border-emerald-500/30 hover:bg-emerald-500/25
              disabled:opacity-30 disabled:cursor-not-allowed
              transition-all flex items-center gap-2 text-sm font-medium"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}


/* ─── User Message Bubble ─── */
function UserMessage({ content }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-br-md bg-emerald-500/15 border border-emerald-500/20">
        <p className="text-sm text-[var(--text-primary)]">{content}</p>
      </div>
    </div>
  );
}


/* ─── Assistant Message ─── */
function AssistantMessage({ message, showAudit, onToggleAudit, onFollowUp }) {
  const confConfig = CONFIDENCE_CONFIG[message.confidence] || CONFIDENCE_CONFIG.Medium;
  const ConfIcon = confConfig.icon;

  return (
    <div className="space-y-3">
      {/* Main response card */}
      <div className="glass-card p-5">
        {/* Confidence badge + timing */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold border ${confConfig.color}`}>
            <ConfIcon className="w-3 h-3" />
            {message.confidence} Confidence
          </span>
          {message.queryContext?.intent && (
            <span className="px-2.5 py-1 rounded-full text-[10px] font-medium bg-[var(--surface-tertiary)] text-[var(--text-tertiary)]">
              {message.queryContext.intent.replace(/_/g, " ")}
            </span>
          )}
          {message.elapsed > 0 && (
            <span className="flex items-center gap-1 text-[10px] text-[var(--text-muted)] ml-auto">
              <Clock className="w-3 h-3" />
              {message.elapsed}s
            </span>
          )}
        </div>

        {/* Explanation text */}
        <div className="prose prose-sm prose-invert max-w-none">
          <div className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
            {message.content}
          </div>
        </div>

        {/* Confidence reason */}
        {message.confidenceReason && (
          <p className="mt-3 text-[11px] text-[var(--text-muted)] italic">
            Confidence: {message.confidenceReason}
          </p>
        )}
      </div>

      {/* Why this answer? — Pipeline audit trail */}
      <button
        onClick={onToggleAudit}
        className="flex items-center gap-2 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
      >
        <Shield className="w-3.5 h-3.5" />
        Why this answer?
        {showAudit ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {showAudit && (
        <div className="glass-card p-4 space-y-3">
          <h4 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
            Pipeline Execution Log
          </h4>
          {message.pipelineLog?.map((step, i) => {
            const config = NODE_CONFIG[step.node] || {};
            const Icon = config.icon || Brain;
            return (
              <div key={i} className="flex items-start gap-3 text-xs">
                <div className={`mt-0.5 ${step.status === "complete" ? config.color : "text-red-400"}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[var(--text-primary)]">
                      {config.label || step.node}
                    </span>
                    <span className="text-[var(--text-muted)]">{step.duration_ms}ms</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                      step.status === "complete" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                    }`}>
                      {step.status}
                    </span>
                  </div>
                  <p className="text-[var(--text-tertiary)] mt-0.5 truncate">{step.details}</p>
                </div>
              </div>
            );
          })}

          {/* Key findings from analysis */}
          {message.analysisResult?.key_findings?.length > 0 && (
            <div className="pt-3 border-t border-[var(--border-secondary)]">
              <h5 className="text-[10px] font-semibold text-[var(--text-tertiary)] uppercase mb-2">
                Statistical Evidence
              </h5>
              {message.analysisResult.key_findings.map((finding, i) => (
                <p key={i} className="text-xs text-[var(--text-secondary)] mb-1">
                  • {finding}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


/* ─── Error Message ─── */
function ErrorMessage({ content }) {
  return (
    <div className="glass-card p-4 border-l-4 border-l-red-500">
      <div className="flex items-start gap-2">
        <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-red-300">{content}</p>
      </div>
    </div>
  );
}
