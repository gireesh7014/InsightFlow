/**
 * API CLIENT — Communicates with the FastAPI Backend
 * ===================================================
 * This module centralizes all backend API calls in one place.
 * 
 * WHY A SEPARATE API MODULE?
 *   Instead of writing fetch() calls in every component, we put them
 *   here. Benefits:
 *   1. One place to change the API URL (dev vs production)
 *   2. Consistent error handling
 *   3. Easy to add auth headers later (Week 4)
 *   4. Components stay clean — they just call analyzeCSV(file)
 * 
 * HOW fetch() WORKS:
 *   fetch() is the browser's built-in HTTP client. It returns a Promise
 *   (async operation). We use async/await to write it like synchronous code.
 *   
 *   const response = await fetch(url)  // Send request, wait for response
 *   const data = await response.json() // Parse JSON body
 */

// Backend URL — change this when deploying
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Upload a CSV file and get analysis results.
 * 
 * HOW FILE UPLOAD WORKS:
 *   HTML forms normally send data as URL-encoded strings.
 *   Files need a different format: multipart/form-data.
 *   
 *   FormData is the JavaScript API for building multipart requests:
 *   1. Create a FormData object
 *   2. Append the file with a key name ("file")
 *   3. fetch() automatically sets the right Content-Type header
 *   
 *   On the backend, FastAPI's UploadFile parameter reads this.
 * 
 * @param {File} file - The CSV file from the file input
 * @returns {Promise<Object>} Analysis results
 */
export async function analyzeCSV(file) {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: "POST",
      body: formData,
      // NOTE: Do NOT set Content-Type header manually!
      // fetch() sets it automatically with the correct boundary
      // for multipart/form-data. Setting it yourself breaks the upload.
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(
        errorData?.detail?.detail || 
        errorData?.detail || 
        `Analysis failed (HTTP ${response.status})`
      );
    }

    return await response.json();
  } catch (error) {
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      throw new Error(
        "Cannot connect to the backend server. Make sure it's running on port 8000."
      );
    }
    throw error;
  }
}

/**
 * Fetch upload history from the backend.
 * 
 * @returns {Promise<Array>} List of past uploads
 */
export async function getHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/history`);
    if (!response.ok) {
      throw new Error(`Failed to fetch history (HTTP ${response.status})`);
    }
    return await response.json();
  } catch (error) {
    console.error("History fetch failed:", error);
    return [];
  }
}

/**
 * Check if the backend is healthy.
 * 
 * @returns {Promise<boolean>} true if backend is reachable
 */
export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}


/**
 * Send a natural language query about uploaded data.
 * 
 * @param {string} query - The question to ask
 * @param {string} filename - The CSV filename to query against
 * @returns {Promise<Object>} Pipeline response with explanation
 */
export async function queryData(query, filename) {
  try {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, filename }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(
        errorData?.detail || `Query failed (HTTP ${response.status})`
      );
    }

    return await response.json();
  } catch (error) {
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      throw new Error(
        "Cannot connect to backend. Make sure it's running on port 8000."
      );
    }
    throw error;
  }
}


/**
 * Stream query results via Server-Sent Events (SSE).
 * 
 * HOW SSE WORKS IN THE BROWSER:
 *   EventSource is the browser's built-in SSE client.
 *   1. Opens a long-lived connection to the server
 *   2. Server sends events as they happen
 *   3. onmessage fires for each event
 *   4. Connection auto-reconnects on failure
 *   
 *   Unlike WebSockets, SSE is one-directional (server → client)
 *   and uses standard HTTP. Perfect for our pipeline status updates.
 * 
 * @param {string} query - The question to ask
 * @param {string} filename - The CSV filename
 * @param {Function} onEvent - Callback fired for each pipeline event
 * @returns {EventSource} The connection (call .close() to stop)
 */
export function streamQuery(query, filename, onEvent) {
  const params = new URLSearchParams({ query, filename });
  const url = `${API_BASE_URL}/query/stream?${params.toString()}`;
  
  const eventSource = new EventSource(url);
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent(data);
      
      // Close connection when pipeline is done
      if (data.type === "pipeline_complete" || data.type === "pipeline_error") {
        eventSource.close();
      }
    } catch (e) {
      console.error("Failed to parse SSE event:", e);
    }
  };
  
  eventSource.onerror = (error) => {
    console.error("SSE connection error:", error);
    onEvent({ type: "pipeline_error", error: "Connection lost" });
    eventSource.close();
  };
  
  return eventSource;
}
