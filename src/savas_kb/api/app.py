"""
FastAPI application for the Savas Knowledge Base.

Provides REST API endpoints for search and alerts.
"""

from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..search import SearchEngine
from ..models import SourceType


app = FastAPI(
    title="Savas Knowledge Base API",
    description="Unified search across company data sources",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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
    """Get knowledge base statistics."""
    from ..storage import ChromaStore
    store = ChromaStore()
    return {
        "total_chunks": store.count(),
    }
