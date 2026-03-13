"""disclosure-multiagent FastAPI backend.

Usage:
    PYTHONPATH=scripts:. uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ をインポートパスに追加
_PROJECT_ROOT = Path(__file__).parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import edinet, analyze, status, checklist, checklist_eval, checklist_stats, scoring, step_execute, a2a

app = FastAPI(
    title="disclosure-multiagent API",
    description="有価証券報告書の開示変更分析パイプライン",
    version="1.0.0",
)

# CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(edinet.router)
app.include_router(analyze.router)
app.include_router(status.router)
app.include_router(checklist.router)
app.include_router(checklist_eval.router)
app.include_router(checklist_stats.router)
app.include_router(scoring.router)
app.include_router(step_execute.router)
app.include_router(a2a.router)


@app.get("/.well-known/agent-card.json", include_in_schema=False)
async def agent_card_well_known():
    """A2A Agent Card を標準パス /.well-known/agent-card.json で提供する。"""
    _card_path = _PROJECT_ROOT / ".well-known" / "agent-card.json"
    if not _card_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Agent Card not found"})
    return JSONResponse(content=json.loads(_card_path.read_text(encoding="utf-8")))


@app.get("/api/health")
async def health():
    """サービス稼働確認エンドポイント。

    Returns:
        dict: {"status": "ok", "service": "disclosure-multiagent"}
    """
    return {"status": "ok", "service": "disclosure-multiagent"}
