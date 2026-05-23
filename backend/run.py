"""
UVICORN LAUNCHER
================
This script starts the FastAPI development server.

WHAT IS UVICORN?
  Uvicorn is an ASGI server — it translates HTTP requests into
  Python function calls that FastAPI can handle.
  
  Think of it as the "middleman" between the internet and your code:
    Browser → HTTP Request → Uvicorn → FastAPI → Your Code
    
  ASGI (Asynchronous Server Gateway Interface) is the modern
  replacement for WSGI. It supports async/await and WebSockets.

FLAGS:
  --reload: Automatically restart when you change code (development only!)
  --host 0.0.0.0: Accept connections from any IP (not just localhost)
  --port 8000: Listen on port 8000

USAGE:
  python run.py
  
  Then open http://localhost:8000/docs for the Swagger UI
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",     # "module:variable" — import 'app' from 'app.main'
        host="0.0.0.0",
        port=8000,
        reload=True,         # Auto-restart on code changes (dev only!)
        log_level="info"
    )
