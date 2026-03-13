"""Pipeline service - runs M1-M5 in background with progress tracking."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Callable

# scripts/ をインポートパスに追加
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from m1_pdf_agent import extract_report  # noqa: E402
from m2_law_agent import load_law_context  # noqa: E402
from m3_gap_analysis_agent import analyze_gaps, GapItem as M3GapItem  # noqa: E402
from m4_proposal_agent import generate_proposals, generate_all_proposals_batch, ProposalSet  # noqa: E402
from m5_report_agent import generate_report, _m3_gap_to_m4_gap  # noqa: E402

from api.models.schemas import (
    PipelineStep,
    PipelineStatus,
    AnalysisResult,
    GapItemResponse,
    NoGapItemResponse,
    GapSummaryResponse,
    ProposalResponse,
    ProposalSetResponse,
)

logger = logging.getLogger(__name__)

PIPELINE_STEPS = [
    "PDF読取",
    "法令確認",
    "ギャップ分析",
    "改善提案",
    "レポート生成",
]

# In-memory task store
_tasks: dict[str, PipelineStatus] = {}

# Step execution mode stores (cmd_360k_a2d)
_step_cache: dict[str, dict] = {}   # task_id → {"m1": StructuredReport, ...}
_step_params: dict[str, dict] = {}  # task_id → {pdf_path, company_name, ...}

STAGE_SEQUENCE = ["m1", "m2", "m3", "m4", "m5"]


def get_task(task_id: str) -> Optional[PipelineStatus]:
    """タスクIDに対応するパイプライン状態を返す。

    Args:
        task_id: create_task() が返す8文字の識別子。

    Returns:
        PipelineStatus: タスクが存在する場合。タスク不在時は None。
    """
    return _tasks.get(task_id)


def create_task() -> str:
    """新規パイプラインタスクをインメモリストアに登録し、タスクIDを返す。

    M1〜M5 の各ステップを "pending" 状態で初期化する。

    Returns:
        str: 8文字のランダムなタスクID（UUID v4 の先頭8文字）。
    """
    task_id = str(uuid.uuid4())[:8]
    steps = [
        PipelineStep(step=i + 1, name=name, status="pending")
        for i, name in enumerate(PIPELINE_STEPS)
    ]
    _tasks[task_id] = PipelineStatus(
        task_id=task_id, status="queued", steps=steps
    )
    return task_id


def create_task_step(
    pdf_path: str,
    company_name: str,
    fiscal_year: int,
    fiscal_month_end: int,
    level: str,
    use_mock: bool = True,
    doc_type: str = "yuho",
    use_debug: bool = False,
) -> str:
    """ステップ実行モード用タスクを作成し、タスクIDを返す。"""
    task_id = str(uuid.uuid4())[:8]
    steps = [
        PipelineStep(step=i + 1, name=name, status="pending")
        for i, name in enumerate(PIPELINE_STEPS)
    ]
    _tasks[task_id] = PipelineStatus(
        task_id=task_id,
        status="queued",
        steps=steps,
        execution_mode="step",
        next_stage="m1",
    )
    _step_cache[task_id] = {}
    _step_params[task_id] = {
        "pdf_path": pdf_path,
        "company_name": company_name,
        "fiscal_year": fiscal_year,
        "fiscal_month_end": fiscal_month_end,
        "level": level,
        "use_mock": use_mock,
        "doc_type": doc_type,
        "use_debug": use_debug,
    }
    return task_id


def serialize_step_output(stage: str, output: Any) -> dict[str, Any]:
    """各ステージの生出力をJSON-friendlyなdictサマリに変換する。

    CR3-1〜CR3-4 (cmd_360k_a2f): key名をTypeScript型定義に合わせた。
    """
    if stage == "m1":
        report = output
        return {
            "section_count": len(report.sections),
            "company_name": report.company_name or "",
            "fiscal_year": report.fiscal_year,
            "document_id": report.document_id,
            "sections": [
                {
                    "section_id": s.section_id,
                    "heading": s.heading,
                    "text_excerpt": s.text[:200] if s.text else "",
                    "char_count": len(s.text) if s.text else 0,
                }
                for s in report.sections
            ],
        }
    elif stage == "m2":
        law = output
        warnings_list = list(law.warnings) if law.warnings else []
        return {
            "applied_count": len(law.applicable_entries),
            "warning_count": len(warnings_list),
            "warnings": warnings_list,
            "missing_categories": law.missing_categories,
            "entries": [
                {
                    "id": getattr(e, "id", ""),
                    "title": getattr(e, "title", str(e)),
                    "category": getattr(e, "category", ""),
                    "source_confirmed": getattr(e, "source_confirmed", None),
                }
                for e in law.applicable_entries
            ],
        }
    elif stage == "m3":
        gap = output
        return {
            "total_gaps": gap.summary.total_gaps,
            "by_change_type": gap.summary.by_change_type,
            "gaps": [
                {
                    "gap_id": g.gap_id,
                    "section_heading": g.section_heading,
                    "change_type": g.change_type,
                    "has_gap": g.has_gap,
                    "gap_description": g.gap_description or "",
                    "disclosure_item": g.disclosure_item,
                    "confidence": g.confidence,
                    "reference_law_title": getattr(g, "reference_law_title", ""),
                    "reference_url": getattr(g, "reference_url", ""),
                    "evidence_hint": getattr(g, "evidence_hint", "") or "",
                }
                for g in gap.gaps
            ],
        }
    elif stage == "m4":
        proposals = output
        return {
            "proposals_count": len(proposals),
            "proposals": [
                {
                    "gap_id": ps.gap_id,
                    "disclosure_item": ps.disclosure_item,
                    "reference_law_id": getattr(ps, "reference_law_id", ""),
                    "matsu": {
                        "text": ps.matsu.text or "",
                        "char_count": len(ps.matsu.text) if ps.matsu.text else 0,
                        "status": getattr(ps.matsu, "status", "pass"),
                        "level": "matsu",
                    },
                    "take": {
                        "text": ps.take.text or "",
                        "char_count": len(ps.take.text) if ps.take.text else 0,
                        "status": getattr(ps.take, "status", "pass"),
                        "level": "take",
                    },
                    "ume": {
                        "text": ps.ume.text or "",
                        "char_count": len(ps.ume.text) if ps.ume.text else 0,
                        "status": getattr(ps.ume, "status", "pass"),
                        "level": "ume",
                    },
                }
                for ps in proposals
            ],
        }
    elif stage == "m5":
        return {
            "char_count": len(output),
            "report_markdown": output,
        }
    return {}


def _build_analysis_result(
    company_display: str,
    fiscal_year: int,
    level: str,
    gap_result: Any,
    proposals: list,
    report_md: str,
) -> AnalysisResult:
    """GapAnalysisResult + ProposalSet[] + report_md から AnalysisResult を構築する。"""
    return AnalysisResult(
        company_name=company_display,
        fiscal_year=fiscal_year,
        level=level,
        summary=GapSummaryResponse(
            total_gaps=gap_result.summary.total_gaps,
            by_change_type=gap_result.summary.by_change_type,
        ),
        gaps=[
            GapItemResponse(
                gap_id=g.gap_id,
                section_heading=g.section_heading,
                change_type=g.change_type,
                has_gap=g.has_gap,
                disclosure_item=g.disclosure_item,
                reference_law_title=g.reference_law_title,
                reference_url=g.reference_url,
                evidence_hint=g.evidence_hint,
                confidence=g.confidence,
                gap_description=g.gap_description,
            )
            for g in gap_result.gaps
        ],
        no_gap_items=[
            NoGapItemResponse(
                disclosure_item=ng.disclosure_item,
                reference_law_id=ng.reference_law_id,
                evidence_hint=ng.evidence_hint,
            )
            for ng in gap_result.no_gap_items
        ],
        proposals=[
            ProposalSetResponse(
                gap_id=ps.gap_id,
                disclosure_item=ps.disclosure_item,
                reference_law_id=ps.reference_law_id,
                matsu=ProposalResponse(
                    level="松",
                    text=ps.matsu.text,
                    char_count=ps.matsu.quality.char_count,
                    status=ps.matsu.status,
                ),
                take=ProposalResponse(
                    level="竹",
                    text=ps.take.text,
                    char_count=ps.take.quality.char_count,
                    status=ps.take.status,
                ),
                ume=ProposalResponse(
                    level="梅",
                    text=ps.ume.text,
                    char_count=ps.ume.quality.char_count,
                    status=ps.ume.status,
                ),
            )
            for ps in proposals
        ],
        report_markdown=report_md,
    )


def _update_step(task_id: str, step_idx: int, status: str, detail: str = "") -> None:
    task = _tasks.get(task_id)
    if not task:
        return
    task.steps[step_idx].status = status
    task.steps[step_idx].detail = detail
    task.current_step = step_idx + 1
    task.status = "running"


async def run_step_async(task_id: str, stage: str) -> dict[str, Any]:
    """ステップ実行モードで1ステージだけ実行し、シリアライズ済み出力を返す。

    Args:
        task_id: create_task_step() が返したタスクID。
        stage: 実行するステージ名。"m1"|"m2"|"m3"|"m4"|"m5"。

    Returns:
        dict: serialize_step_output() の返り値（JSONシリアライズ済み出力サマリ）。

    Raises:
        ValueError: タスクが存在しない、またはステージ名が不正な場合。
        Exception:  各ステージの実行中にエラーが発生した場合（task.status="error" にも設定）。
    """
    task = _tasks.get(task_id)
    params = _step_params.get(task_id)
    cache = _step_cache.get(task_id)

    if task is None or params is None or cache is None:
        raise ValueError(f"タスク {task_id} が存在しないか、ステップ実行モードで作成されていません")
    if stage not in STAGE_SEQUENCE:
        raise ValueError(f"不明なステージ: {stage}。有効値: {STAGE_SEQUENCE}")

    stage_idx = STAGE_SEQUENCE.index(stage)
    loop = asyncio.get_event_loop()

    # 環境変数でLLMモードを切り替え
    if params["use_debug"]:
        os.environ["USE_DEBUG_LLM"] = "true"
    elif params["use_mock"]:
        os.environ["USE_MOCK_LLM"] = "true"

    _update_step(task_id, stage_idx, "running")

    try:
        if stage == "m1":
            result = await loop.run_in_executor(
                None,
                lambda: extract_report(
                    pdf_path=params["pdf_path"],
                    company_name=params["company_name"],
                    fiscal_year=params["fiscal_year"],
                    fiscal_month_end=params["fiscal_month_end"],
                    doc_type=params["doc_type"],
                ),
            )
            detail = f"{len(result.sections)}セクション検出"

        elif stage == "m2":
            result = await loop.run_in_executor(
                None,
                lambda: load_law_context(
                    fiscal_year=params["fiscal_year"],
                    fiscal_month_end=params["fiscal_month_end"],
                ),
            )
            detail = f"{len(result.applicable_entries)}件の法令エントリ"

        elif stage == "m3":
            structured_report = cache.get("m1")
            law_context = cache.get("m2")
            if structured_report is None or law_context is None:
                raise ValueError("M3にはM1・M2の完了が必要です（m1/m2 キャッシュが未設定）")
            result = await loop.run_in_executor(
                None,
                lambda: analyze_gaps(
                    report=structured_report,
                    law_context=law_context,
                    use_mock=params["use_mock"],
                    use_debug=params["use_debug"],
                ),
            )
            has_gap_count = sum(1 for g in result.gaps if g.has_gap)
            detail = f"ギャップ{has_gap_count}件検出"

        elif stage == "m4":
            gap_result = cache.get("m3")
            if gap_result is None:
                raise ValueError("M4にはM3の完了が必要です（m3 キャッシュが未設定）")
            proposals: list[ProposalSet] = []

            def _gen_proposals() -> None:
                gap_items_with_gap = [
                    _m3_gap_to_m4_gap(gap) for gap in gap_result.gaps if gap.has_gap
                ]
                if params["use_debug"] and gap_items_with_gap:
                    try:
                        batch_results = generate_all_proposals_batch(gap_items_with_gap)
                        proposals.extend(batch_results)
                        return
                    except Exception as e:
                        logger.warning("[step M4 batch] バッチ失敗、逐次処理にフォールバック: %s", e)
                for m4_gap in gap_items_with_gap:
                    ps = generate_proposals(m4_gap, use_debug=params["use_debug"])
                    proposals.append(ps)

            await loop.run_in_executor(None, _gen_proposals)
            result = proposals
            detail = f"{len(proposals)}件の提案セット"

        else:  # stage == "m5"
            structured_report = cache.get("m1")
            law_context = cache.get("m2")
            gap_result = cache.get("m3")
            proposals_list = cache.get("m4")
            if any(v is None for v in [structured_report, law_context, gap_result, proposals_list]):
                missing = [s for s in ["m1", "m2", "m3", "m4"] if cache.get(s) is None]
                raise ValueError(f"M5にはM1-M4の完了が必要です（未実行: {missing}）")
            result = await loop.run_in_executor(
                None,
                lambda: generate_report(
                    structured_report=structured_report,
                    law_context=law_context,
                    gap_result=gap_result,
                    proposal_set=proposals_list,
                    level=params["level"],
                ),
            )
            detail = f"{len(result)}文字のレポート"

        # ─── 成功後処理 ───────────────────────────────────────────
        # 生出力をキャッシュに保存
        cache[stage] = result

        # シリアライズしてtask.step_outputsに保存
        serialized = serialize_step_output(stage, result)
        task.step_outputs[stage] = serialized

        # ステップ状態更新（_update_stepはtask.statusを"running"に設定する点に注意）
        _update_step(task_id, stage_idx, "done", detail)

        # next_stage を進める
        if stage_idx + 1 < len(STAGE_SEQUENCE):
            task.next_stage = STAGE_SEQUENCE[stage_idx + 1]
        else:
            # M5完了 → パイプライン全完了
            task.next_stage = "done"
            task.status = "done"
            company_display = cache["m1"].company_name or params["company_name"] or "分析対象企業"
            task.result = _build_analysis_result(
                company_display=company_display,
                fiscal_year=params["fiscal_year"],
                level=params["level"],
                gap_result=cache["m3"],
                proposals=cache["m4"],
                report_md=cache["m5"],
            )

        return serialized

    except Exception as e:
        logger.exception("[run_step_async] stage=%s task=%s エラー", stage, task_id)
        _update_step(task_id, stage_idx, "error", str(e))
        task.status = "error"
        task.error = str(e)
        raise


async def run_pipeline_async(
    task_id: str,
    pdf_path: str,
    company_name: str,
    fiscal_year: int,
    fiscal_month_end: int,
    level: str,
    use_mock: bool = True,
    doc_type: str = "yuho",
    use_debug: bool = False,
    profile_name: Optional[str] = None,
) -> None:
    """Execute the M1-M5 pipeline in a background thread."""
    task = _tasks.get(task_id)
    if not task:
        return

    try:
        # Set mock mode / debug mode via environment variables
        if use_debug:
            os.environ["USE_DEBUG_LLM"] = "true"
        elif use_mock:
            os.environ["USE_MOCK_LLM"] = "true"

        # Resolve profile_dir: profile_name 指定時は profiles/ ディレクトリを使用
        _project_root = Path(__file__).parent.parent.parent
        profile_dir: Optional[str] = None
        if profile_name is not None:
            profile_dir = str(_project_root / "profiles")

        loop = asyncio.get_event_loop()

        # Step 1: M1 PDF解析
        _update_step(task_id, 0, "running")
        structured_report = await loop.run_in_executor(
            None,
            lambda: extract_report(
                pdf_path=pdf_path,
                company_name=company_name,
                fiscal_year=fiscal_year,
                fiscal_month_end=fiscal_month_end,
                doc_type=doc_type,
            ),
        )
        company_display = structured_report.company_name or company_name or "分析対象企業"
        _update_step(task_id, 0, "done", f"{len(structured_report.sections)}セクション検出")

        # Step 2: M2 法令取得（profile_dir 指定時は profiles/ も追加ロード）
        _update_step(task_id, 1, "running")
        law_context = await loop.run_in_executor(
            None,
            lambda: load_law_context(
                fiscal_year=fiscal_year,
                fiscal_month_end=fiscal_month_end,
                profile_dir=profile_dir,
            ),
        )
        _update_step(task_id, 1, "done", f"{len(law_context.applicable_entries)}件の法令エントリ")

        # Step 3: M3 ギャップ分析
        _update_step(task_id, 2, "running")
        gap_result = await loop.run_in_executor(
            None,
            lambda: analyze_gaps(
                report=structured_report,
                law_context=law_context,
                use_mock=use_mock,
                use_debug=use_debug,
            ),
        )
        has_gap_count = sum(1 for g in gap_result.gaps if g.has_gap)
        _update_step(task_id, 2, "done", f"ギャップ{has_gap_count}件検出")

        # Step 4: M4 提案生成
        _update_step(task_id, 3, "running")
        proposals: list[ProposalSet] = []

        def _generate_proposals():
            gap_items_with_gap = [
                _m3_gap_to_m4_gap(gap) for gap in gap_result.gaps if gap.has_gap
            ]
            if use_debug and gap_items_with_gap:
                # バッチIPC: 全ギャップを1回のリクエストで処理
                try:
                    batch_results = generate_all_proposals_batch(gap_items_with_gap)
                    proposals.extend(batch_results)
                    return
                except Exception as e:
                    logger.warning("[pipeline M4 batch] バッチ失敗、逐次処理にフォールバック: %s", e)
            # 逐次処理（use_debug=False またはバッチ失敗時）
            for m4_gap in gap_items_with_gap:
                ps = generate_proposals(m4_gap, use_debug=use_debug)
                proposals.append(ps)

        await loop.run_in_executor(None, _generate_proposals)
        _update_step(task_id, 3, "done", f"{len(proposals)}件の提案セット")

        # Step 5: M5 レポート統合
        _update_step(task_id, 4, "running")
        report_md = await loop.run_in_executor(
            None,
            lambda: generate_report(
                structured_report=structured_report,
                law_context=law_context,
                gap_result=gap_result,
                proposal_set=proposals,
                level=level,
            ),
        )
        _update_step(task_id, 4, "done", f"{len(report_md)}文字のレポート")

        # Build result
        result = AnalysisResult(
            company_name=company_display,
            fiscal_year=fiscal_year,
            level=level,
            summary=GapSummaryResponse(
                total_gaps=gap_result.summary.total_gaps,
                by_change_type=gap_result.summary.by_change_type,
            ),
            gaps=[
                GapItemResponse(
                    gap_id=g.gap_id,
                    section_heading=g.section_heading,
                    change_type=g.change_type,
                    has_gap=g.has_gap,
                    disclosure_item=g.disclosure_item,
                    reference_law_title=g.reference_law_title,
                    reference_url=g.reference_url,
                    evidence_hint=g.evidence_hint,
                    confidence=g.confidence,
                    gap_description=g.gap_description,
                )
                for g in gap_result.gaps
            ],
            no_gap_items=[
                NoGapItemResponse(
                    disclosure_item=ng.disclosure_item,
                    reference_law_id=ng.reference_law_id,
                    evidence_hint=ng.evidence_hint,
                )
                for ng in gap_result.no_gap_items
            ],
            proposals=[
                ProposalSetResponse(
                    gap_id=ps.gap_id,
                    disclosure_item=ps.disclosure_item,
                    reference_law_id=ps.reference_law_id,
                    matsu=ProposalResponse(
                        level="松",
                        text=ps.matsu.text,
                        char_count=ps.matsu.quality.char_count,
                        status=ps.matsu.status,
                    ),
                    take=ProposalResponse(
                        level="竹",
                        text=ps.take.text,
                        char_count=ps.take.quality.char_count,
                        status=ps.take.status,
                    ),
                    ume=ProposalResponse(
                        level="梅",
                        text=ps.ume.text,
                        char_count=ps.ume.quality.char_count,
                        status=ps.ume.status,
                    ),
                )
                for ps in proposals
            ],
            report_markdown=report_md,
        )

        task.result = result
        task.status = "done"

    except Exception as e:
        logger.exception("Pipeline error for task %s", task_id)
        task.status = "error"
        task.error = str(e)
        # Mark current step as error
        for step in task.steps:
            if step.status == "running":
                step.status = "error"
                step.detail = str(e)
