"""開示変更スコアリング API ルーター (T012)

エンドポイント:
  POST /api/scoring/document  → ScoringResponse
  GET  /api/scoring/history   → ScoringHistoryResponse（最新10件）
  POST /api/scoring/tier      → TierScoreResponse（松竹梅ティアスコア）
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
    """開示文書テキストから松竹梅ティアスコアを算出する (C06差替: cmd_375k_a7)。

    計算方法（実 tier_requirement データ接続済み）:
      - laws/*.yaml の tier_requirement フィールドを使用（68エントリ）
      - 選択ティアの「必須」項目数を分母に
      - 開示テキストのキーワードマッチでカバー済み必須項目数を算出
      - score = (カバー済み必須項目 / 全必須項目) × 100
      - 梅ライン: 60点以上 / 竹ライン: 80点以上 / 松ライン: 95点以上
    """
    if not request.disclosure_text.strip():
        raise HTTPException(status_code=400, detail="disclosure_text が空です")

    # target_tier から tier_level（YAML キー）へのマッピング
    _tier_to_level: dict[str, str] = {"梅": "ume", "竹": "take", "松": "matsu"}

    # 実データ接続: laws/*.yaml から tier_requirement 付き68エントリ取得
    law_entries = scoring_service.load_law_entries()

    # キーワードマッチングで gap_results 生成（M3 LLM の代替）
    gap_results = scoring_service._derive_gap_results(request.disclosure_text, law_entries)

    # target_tier が未指定なら一旦「梅」でスコアを計算してからラベルで次ティアを判定
    initial_level = _tier_to_level.get(request.target_tier or "梅", "ume")
    tier_score = scoring_service.compute_tier_score(gap_results, law_entries, tier_level=initial_level)
    tier_label = scoring_service.get_tier_label(tier_score)

    # 実際に使うティアレベル: target_tier 指定があればそれ、なければ次ティアへ
    _next_tier_map = {"未達": "梅", "梅": "竹", "竹": "松", "松": None}
    effective_target = request.target_tier or _next_tier_map.get(tier_label)
    effective_level = _tier_to_level.get(effective_target or "梅", "ume")

    # target_tier が指定された場合はそのティアで再スコア算出
    if request.target_tier:
        tier_score = scoring_service.compute_tier_score(gap_results, law_entries, tier_level=effective_level)
        tier_label = scoring_service.get_tier_label(tier_score)

    # アップグレード項目: 実データから未カバーの「必須」項目を取得
    upgrade_items: list[str] = []
    if effective_target:
        upgrade_items = scoring_service._get_upgrade_items_from_laws(
            gap_results, law_entries, effective_level
        )

    return TierScoreResponse(
        tier_score=tier_score,
        tier_label=tier_label,
        upgrade_items=upgrade_items,
    )
