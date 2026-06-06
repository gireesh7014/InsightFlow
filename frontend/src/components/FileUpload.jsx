/**
 * FILE UPLOAD COMPONENT — Drag & Drop CSV Upload
 * ================================================
 * This is the main interaction point — users drag a CSV file onto
 * the dropzone or click to browse.
 * 
 * REACT CONCEPTS USED:
 *   - useState: Stores component state (isDragging, file, error)
 *   - useRef: References a DOM element (the hidden file input)
 *   - useCallback: Memoizes event handlers for performance
 *   - Event handling: onDragOver, onDragLeave, onDrop, onChange
 * 
 * HTML5 DRAG & DROP API:
 *   The browser fires these events when dragging files:
 *   1. dragenter → file enters the dropzone area
 *   2. dragover  → file is hovering over the area (must preventDefault!)
 *   3. dragleave → file leaves the area
 *   4. drop      → file is released on the area
 *   
 *   e.preventDefault() is CRITICAL in dragover — without it, the browser
 *   opens the file instead of letting your code handle it.
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { Upload, FileSpreadsheet, X, Loader2, AlertCircle } from "lucide-react";

/**
 * @param {Object} props
 * @param {Function} props.onFileSelect - Called with the selected File object
 * @param {boolean} props.isLoading - True while analysis is in progress
 */
export default function FileUpload({ onFileSelect, isLoading }) {
  // ─── State ─────────────────────────────────────────────
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState(null);
  
  // useRef gives us a reference to the hidden <input type="file">
  // so we can trigger it programmatically when the user clicks the dropzone
  const fileInputRef = useRef(null);

  // ─── File Validation ───────────────────────────────────
  const validateFile = useCallback((file) => {
    if (!file) return "No file selected";
    
    if (!file.name.toLowerCase().endsWith(".csv")) {
      return "Please upload a CSV file. Other formats are not supported yet.";
    }
    
    // 50MB limit (same as backend)
    if (file.size > 50 * 1024 * 1024) {
      return `File too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum: 50MB`;
    }
    
    return null; // No error = valid
  }, []);

  // ─── Handle file selection (from drop or click) ────────
  const handleFile = useCallback(
    (file) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        setSelectedFile(null);
        return;
      }
      
      setError(null);
      setSelectedFile(file);
      onFileSelect(file); // Tell parent component about the file
    },
    [validateFile, onFileSelect]
  );

  // ─── Drag & Drop Event Handlers ────────────────────────

  const handleDragOver = useCallback((e) => {
    e.preventDefault(); // MUST prevent default or drop won't work!
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      // e.dataTransfer.files contains the dropped file(s)
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFile(files[0]); // Take only the first file
      }
    },
    [handleFile]
  );

  // ─── Click to Browse Handler ───────────────────────────
  const handleClick = () => {
    if (!isLoading) {
      fileInputRef.current?.click(); // Trigger the hidden file input
    }
  };

  const handleInputChange = (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  };

  // ─── Clear Selection ───────────────────────────────────
  const clearFile = (e) => {
    e.stopPropagation(); // Don't trigger the dropzone click
    setSelectedFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = ""; // Reset the file input
    }
  };

  // ─── Format file size for display ──────────────────────
  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="w-full">
      {/* Hidden file input — triggered by clicking the dropzone */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        onChange={handleInputChange}
        className="hidden"
        id="csv-upload-input"
      />

      {/* ─── Dropzone ─── */}
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative cursor-pointer rounded-2xl border-2 border-dashed 
          transition-all duration-300 ease-out
          ${isLoading ? "pointer-events-none opacity-60" : ""}
          ${isDragging
            ? "border-emerald-400 bg-emerald-500/5 scale-[1.01] shadow-[0_0_30px_rgba(16,185,129,0.1)]"
            : "border-[var(--border-primary)] bg-[var(--surface-primary)] hover:border-[var(--border-accent)] hover:bg-[var(--surface-secondary)]"
          }
        `}
        id="csv-dropzone"
      >
        <div className="flex flex-col items-center justify-center py-12 px-6">
          {/* Loading state */}
          {isLoading ? (
            <>
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4">
                <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
              </div>
              <p className="text-[var(--text-primary)] font-medium text-lg">
                Analyzing your data...
              </p>
              <p className="text-[var(--text-secondary)] text-sm mt-1">
                Running 20 insight rules, generating charts
              </p>
            </>
          ) : selectedFile ? (
            /* File selected state */
            <>
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4">
                <FileSpreadsheet className="w-8 h-8 text-emerald-400" />
              </div>
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <p className="text-[var(--text-primary)] font-medium text-lg">
                    {selectedFile.name}
                  </p>
                  <p className="text-[var(--text-secondary)] text-sm mt-0.5">
                    {formatSize(selectedFile.size)}
                  </p>
                </div>
                <button
                  onClick={clearFile}
                  className="p-1.5 rounded-lg hover:bg-red-500/10 text-[var(--text-tertiary)] hover:text-red-400 transition-colors"
                  aria-label="Remove file"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </>
          ) : (
            /* Default empty state */
            <>
              <div
                className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-colors duration-300
                  ${isDragging ? "bg-emerald-500/20" : "bg-[var(--surface-tertiary)]"}`}
              >
                <Upload
                  className={`w-8 h-8 transition-colors duration-300
                    ${isDragging ? "text-emerald-400" : "text-[var(--text-tertiary)]"}`}
                />
              </div>
              <p className="text-[var(--text-primary)] font-medium text-lg">
                Drop your CSV file here
              </p>
              <p className="text-[var(--text-secondary)] text-sm mt-1">
                or{" "}
                <span className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2">
                  click to browse
                </span>
              </p>
              <p className="text-[var(--text-muted)] text-xs mt-3">
                Supports CSV files up to 50MB
              </p>
            </>
          )}
        </div>
      </div>

      {/* ─── Error Message ─── */}
      {error && (
        <div className="mt-3 flex items-start gap-2 p-3 rounded-xl bg-red-500/5 border border-red-500/20">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}
    </div>
  );
}
