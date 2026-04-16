"""
main.py — FastAPI application entry point.

FIX: Replaced deprecated @app.on_event("startup") with modern lifespan
     context manager (FastAPI 0.93+).
FIX: /docs always enabled in DEBUG mode (default True for development).
FIX: CORS origins include 127.0.0.1 variants.

Routes:
  POST /api/search          — full orchestrated search (JSON response)
  POST /api/stream          — Server-Sent Events streaming search
  GET  /api/health          — health check
  GET  /api/tools           — list registered tools
  DELETE /api/session/{id}  — clear conversation memory
  WebSocket /ws/{session_id} — WebSocket streaming
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import get_settings

# ── Import tools so they self-register with the tool registry ─────────────────
import tools.web_search          # noqa: F401  — registers web_search tool
import tools.content_extractor   # noqa: F401  — registers extract_webpage_content tool

from agents.orchestrator import OrchestratorAgent
from memory.short_term import short_term_memory
from memory.long_term import long_term_memory
from tools.tool_registry import registry
from utils.logger import logger

settings = get_settings()


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Validate API key early with a clear error message
    try:
        settings.get_anthropic_key()
        logger.info("✅ ANTHROPIC_API_KEY found")
    except RuntimeError as e:
        logger.error(str(e))
        # Don't crash — the error will surface on first request instead

    await long_term_memory.initialize()
    logger.info(f"🔧 Registered tools: {registry.list_names()}")
    logger.info(f"📖 API docs: http://{settings.HOST}:{settings.PORT}/docs")

    yield  # ← app runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("👋 Shutting down...")


# ── App init ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Perplexity-style AI research agent powered by Claude",
    # FIX: docs always available (guarded by DEBUG in production deployments)
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = OrchestratorAgent()


# ── Request / Response models ──────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    route: Optional[str] = Field(
        None,
        description="Force route: 'simple' | 'deep' | 'factual'. Auto-detected if omitted.",
    )


class SearchResponse(BaseModel):
    answer: str
    sources: list
    evaluation: dict
    route: str
    session_id: str
    latency_ms: float
    agent: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check — returns server status and registered tools."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "tools": registry.list_names(),
        "api_key_set": bool(settings.ANTHROPIC_API_KEY),
        "search_api": (
            "tavily" if settings.TAVILY_API_KEY
            else "serpapi" if settings.SERPAPI_KEY
            else "stub (no keys)"
        ),
    }


@app.get("/api/tools", tags=["System"])
async def list_tools():
    """List all registered tools with their JSON schemas."""
    return {"tools": registry.all_definitions()}


@app.post("/api/search", response_model=SearchResponse, tags=["Search"])
async def search(req: SearchRequest):
    """
    Full orchestrated search — returns complete answer after all reasoning steps.
    Use /api/stream for real-time streaming output.
    """
    logger.info(f"[POST /api/search] session={req.session_id[:8]} query='{req.query[:60]}'")
    t0 = time.monotonic()

    # Validate API key before making a request
    try:
        settings.get_anthropic_key()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        result = await orchestrator.process(
            query=req.query,
            session_id=req.session_id,
            force_route=req.route,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    return SearchResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        evaluation={**result.get("evaluation", {}), "latency_ms": latency_ms},
        route=result.get("route", "simple"),
        session_id=req.session_id,
        latency_ms=latency_ms,
        agent=result.get("agent", "OrchestratorAgent"),
    )


@app.post("/api/stream", tags=["Search"])
async def search_stream(req: SearchRequest):
    """
    Streaming search via Server-Sent Events (SSE).

    Each event is: `data: <json>\\n\\n`

    Event types:
    - `thinking` — agent reasoning step (tool call in progress)
    - `text`     — partial answer text
    - `source`   — a cited source URL
    - `evaluation` — quality scores
    - `done`     — stream complete
    - `error`    — something went wrong
    """
    logger.info(f"[POST /api/stream] session={req.session_id[:8]} query='{req.query[:60]}'")

    try:
        settings.get_anthropic_key()
    except RuntimeError as e:
        async def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in orchestrator.stream(
                query=req.query,
                session_id=req.session_id,
            ):
                payload = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            err = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {err}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",         # disable nginx buffering
            "Access-Control-Allow-Origin": "*",  # SSE CORS fix
        },
    )


@app.delete("/api/session/{session_id}", tags=["Session"])
async def clear_session(session_id: str):
    """Clear conversation memory for a given session ID."""
    await short_term_memory.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/api/session/{session_id}/history", tags=["Session"])
async def get_session_history(session_id: str):
    """Get conversation history for a session."""
    history = await short_term_memory.get_history(session_id)
    return {"session_id": session_id, "turns": len(history), "history": history}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_search(websocket: WebSocket, session_id: str):
    """
    WebSocket-based streaming.
    Client sends JSON: {"query": "..."}
    Server streams JSON event objects.
    """
    await websocket.accept()
    logger.info(f"[WS] Connected: {session_id[:8]}")

    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "").strip()
            if not query:
                await websocket.send_json({"type": "error", "content": "Empty query"})
                continue

            async for chunk in orchestrator.stream(query=query, session_id=session_id):
                await websocket.send_json(chunk)

    except WebSocketDisconnect:
        logger.info(f"[WS] Disconnected: {session_id[:8]}")
    except Exception as e:
        logger.error(f"[WS] Error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
