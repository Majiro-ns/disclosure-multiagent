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
    TierScoreRequest,
    TierScoreResponse,
)
from api.services import scoring_service
from api.services.checklist_eval_service import evaluate_and_save

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


@router.post("/tier", response_model=TierScoreResponse)
async def compute_tier_score(request: TierScoreRequest) -> TierScoreResponse:
    """開示文書テキストから松竹梅ティアスコアを算出する (C06 cmd_374k_a7)。

    計算方法（C07完了前モック）:
      - チェックリストカバレッジ（coverage_rate × 100）を tier_score として使用
      - 梅ライン: 60点以上 / 竹ライン: 80点以上 / 松ライン: 95点以上

    C07完了後は compute_tier_score(gap_results, law_entries) に切り替え予定。
    """
    if not request.disclosure_text.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="disclosure_text が空です")

    # チェックリストカバレッジを tier_score のベースとして使用（C07前モック）
    eval_result = evaluate_and_save(request.disclosure_text)
    tier_score = min(100, round(eval_result["coverage_rate"] * 100))

    tier_label = scoring_service.get_tier_label(tier_score)

    # target_tier が未指定なら次のティアを自動設定
    _next_tier_map = {"未達": "梅", "梅": "竹", "竹": "松", "松": None}
    effective_target = request.target_tier or _next_tier_map.get(tier_label)

    upgrade_items: list[str] = []
    if effective_target:
        upgrade_items = scoring_service.get_upgrade_items(tier_score, effective_target)

    return TierScoreResponse(
        tier_score=tier_score,
        tier_label=tier_label,
        upgrade_items=upgrade_items,
    )
