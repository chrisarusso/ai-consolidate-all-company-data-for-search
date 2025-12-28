"""
FastAPI application for the Savas Knowledge Base.

Provides REST API endpoints for search and alerts.
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..search import SearchEngine
from ..models import SourceType

# Frontend dist directory (built by Vite)
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"

app = FastAPI(
    title="Savas Knowledge Base API",
    description="Unified search across company data sources",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "https://internal.savaslabs.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize search engine
engine = SearchEngine()


class SearchRequest(BaseModel):
    """Request body for search endpoint."""
    query: str
    top_k: int = 10
    source_types: Optional[list[str]] = None
    project: Optional[str] = None
    client: Optional[str] = None


class SalesPrepRequest(BaseModel):
    """Request body for sales prep endpoint."""
    prospect_context: str
    top_k: int = 10


class OneOnOneRequest(BaseModel):
    """Request body for 1:1 prep endpoint."""
    team_member_name: str
    days_back: int = 30


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "savas-knowledge-base"}


@app.post("/api/search")
async def search(request: SearchRequest):
    """
    Search the knowledge base.

    Returns an answer with source citations.
    """
    try:
        # Convert source type strings to enums
        source_types = None
        if request.source_types:
            source_types = [SourceType(st) for st in request.source_types]

        response = engine.search(
            query=request.query,
            top_k=request.top_k,
            source_types=source_types,
            project=request.project,
            client=request.client,
        )

        return {
            "query": response.query,
            "answer": response.answer,
            "sources_used": response.sources_used,
            "results": [
                {
                    "score": r.score,
                    "content": r.chunk.content,
                    "source_type": r.chunk.source_type.value,
                    "channel": r.chunk.channel,
                    "timestamp": r.chunk.timestamp.isoformat() if r.chunk.timestamp else None,
                    "author": r.chunk.author,
                    "source_url": r.chunk.source_url,
                }
                for r in response.results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sales-prep")
async def sales_prep(request: SalesPrepRequest):
    """
    Prepare for a sales call.

    Takes prospect context and returns relevant past experience.
    """
    try:
        response = engine.search_for_sales_prep(
            prospect_context=request.prospect_context,
            top_k=request.top_k,
        )

        return {
            "answer": response.answer,
            "sources_used": response.sources_used,
            "results": [
                {
                    "score": r.score,
                    "content": r.chunk.content,
                    "source_type": r.chunk.source_type.value,
                    "channel": r.chunk.channel,
                }
                for r in response.results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/1on1-prep")
async def one_on_one_prep(request: OneOnOneRequest):
    """
    Prepare for a 1:1 meeting.

    Returns recent activity and discussion topics for a team member.
    """
    try:
        response = engine.search_for_1on1_prep(
            team_member_name=request.team_member_name,
            days_back=request.days_back,
        )

        return {
            "team_member": request.team_member_name,
            "answer": response.answer,
            "sources_used": response.sources_used,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def stats():
    """Get knowledge base statistics from both SQLite (raw) and ChromaDB (embedded)."""
    from ..storage import ChromaStore, SQLiteStore

    chroma_store = ChromaStore()
    sqlite_store = SQLiteStore()

    # Get SQLite stats
    sqlite_stats = sqlite_store.get_stats()

    return {
        "chromadb": {
            "total_chunks": chroma_store.count(),
            "description": "Embedded chunks ready for semantic search"
        },
        "sqlite": {
            "description": "Raw data from source APIs",
            "teamwork": {
                "projects": sqlite_stats.get("teamwork_projects", 0),
                "tasks": sqlite_stats.get("teamwork_tasks", 0),
                "messages": sqlite_stats.get("teamwork_messages", 0),
            },
            "harvest": {
                "clients": sqlite_stats.get("harvest_clients", 0),
                "projects": sqlite_stats.get("harvest_projects", 0),
                "time_entries": sqlite_stats.get("harvest_time_entries", 0),
            },
            "fathom": {
                "transcripts": sqlite_stats.get("fathom_transcripts", 0),
            },
            "github": {
                "files": sqlite_stats.get("github_files", 0),
                "issues": sqlite_stats.get("github_issues", 0),
            },
            "drive": {
                "documents": sqlite_stats.get("drive_documents", 0),
            },
        },
    }


# Serve frontend static files (must be after API routes)
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend for all non-API routes (SPA catch-all)."""
        # Try to serve the specific file first
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Fall back to index.html for SPA routing
        return FileResponse(FRONTEND_DIR / "index.html")
