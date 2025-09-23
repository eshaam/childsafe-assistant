# app/api.py

import os  # Standard library for environment variables
from fastapi import FastAPI, Request, HTTPException  # FastAPI for REST API
from fastapi.middleware.cors import CORSMiddleware  # CORS support for frontend
from dotenv import load_dotenv  # For loading .env configuration
from app.langchain_rag import smart_query  # Import main RAG pipeline

# -----------------------------------------------------------------------------
# CONFIGURATION & APP INITIALIZATION
# -----------------------------------------------------------------------------

# Load environment variables from .env file into process environment
load_dotenv()

# Initialize FastAPI application with descriptive title
app = FastAPI(title="ChildSafe RAG API")

# Configure Cross-Origin Resource Sharing (CORS)
# This allows frontend clients (React/Vue/etc.) to make API requests
frontend_url = os.getenv("FRONTEND_URL")
allow_origins = []

# Add production URL if set
if frontend_url:
    allow_origins.append(frontend_url)

# Always add localhost for development
allow_origins.extend([
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000"
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,  # Allow cookies/headers for auth if needed
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------

@app.post("/query")
async def run_query(request: Request):
    """
    POST /query
    Entry point for user queries into the RAG pipeline.
    Accepts JSON payload with:
      - query: str (required)  -> the natural language user query
      - top_k: int (optional)  -> number of retrieved docs (default=5)
    Routes query into smart_query() (LangChain-style orchestration).
    """

    # Parse JSON request body
    data = await request.json()

    # Extract query string; default top_k=5 if not provided
    query_text = data.get("query")
    top_k = data.get("top_k", 5)

    # Validate required input
    if not query_text:
        raise HTTPException(status_code=400, detail="Missing 'query' field")

    # Pass query to orchestrator (smart_query handles local/web modes)
    response = smart_query(query_text, top_k=top_k)

    # Debug logging: show whether pipeline classified as local or web
    mode = response.get("mode", "unknown")
    print(f"Detected mode for query '{query_text}': {mode}")

    # Return structured response (LangChain-style: {"results": ...})
    return {"results": response}


@app.get("/health")
async def health_check():
    """
    GET /health
    Simple health-check endpoint for uptime monitoring.
    Returns {"status": "ok"} if server is healthy.
    """
    return {"status": "ok"}

