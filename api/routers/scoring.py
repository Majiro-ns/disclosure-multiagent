"""開示変更スコアリング API ルーター (T012)

エンドポイント:
  POST /api/scoring/document  → ScoringResponse
  GET  /api/scoring/history   → ScoringHistoryResponse（最新10件）
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models.schemas import (
    MatchedItemBrief,
    ScoringHistoryItem,
    ScoringHistoryResponse,
    ScoringRequest,
    ScoringResponse,
)
from api.services import scoring_service

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.post("/document", response_model=ScoringResponse)
async def score_document(request: ScoringRequest) -> ScoringResponse:
    """開示文書テキストをPOSTし、変更インパクトスコアを返す。

    スコア計算:
    - checklist_coverage_score: チェックリスト一致率（0-100）
    - change_intensity_score: 変更語彙の濃度（0-100）
    - overall_risk_score: 総合リスクスコア（0-100）
    - risk_level: "low" (<40) / "medium" (40-69) / "high" (>=70)
    """
    if not request.disclosure_text.strip():
        raise HTTPException(status_code=400, detail="disclosure_text が空です")
    try:
        result = scoring_service.score_document(request.disclosure_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ScoringResponse(
        score_id=result["score_id"],
        scored_at=result["scored_at"],
        overall_risk_score=result["overall_risk_score"],
        checklist_coverage_score=result["checklist_coverage_score"],
        change_intensity_score=result["change_intensity_score"],
        risk_level=result["risk_level"],
        top_matched_items=[MatchedItemBrief(**it) for it in result["top_matched_items"]],
    )


@router.get("/history", response_model=ScoringHistoryResponse)
async def score_history() -> ScoringHistoryResponse:
    """過去のスコアリング履歴（最新10件）を返す。"""
    rows = scoring_service.get_score_history(limit=10)
    items = [
        ScoringHistoryItem(
            **{k: v for k, v in row.items() if k != "top_matched_items"},
            top_matched_items=[MatchedItemBrief(**it) for it in row["top_matched_items"]],
        )
        for row in rows
    ]
    return ScoringHistoryResponse(history=items, count=len(items))
