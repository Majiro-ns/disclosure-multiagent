"""step_serializers.py
====================
disclosure-multiagent ステップ実行モード用 中間出力シリアライザ。

各エージェント(M1〜M5)の出力 dataclass/str を、UI表示に適した dict に変換する。
API (A2) と UI (A4) が共通で使用するデータ変換層。

cmd_360k_a3f にて作成 (2026-03-14)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from m3_gap_analysis_agent import (
        GapAnalysisResult,
        LawContext,
        StructuredReport,
    )
    from m4_proposal_agent import ProposalSet


def serialize_m1(report: "StructuredReport") -> dict:
    """M1出力（StructuredReport）を UI表示用 dict にシリアライズする。

    Args:
        report: M1エージェントが生成した構造化有報

    Returns:
        {
          "company_name": "株式会社テスト商事",
          "fiscal_year": 2025,
          "total_sections": 18,
          "total_chars": 1856,
          "sections": [
            {"id": "sec_001", "heading": "人的資本", "char_count": 417,
             "preview": "当社は人材を...(先頭200文字)"},
            ...
          ]
        }
    """
    return {
        "company_name": report.company_name,
        "fiscal_year": report.fiscal_year,
        "total_sections": len(report.sections),
        "total_chars": sum(len(s.text) for s in report.sections),
        "sections": [
            {
                "id": s.section_id,
                "heading": s.heading,
                "char_count": len(s.text),
                "preview": s.text[:200],
            }
            for s in report.sections
        ],
    }


def serialize_m2(law_context: "LawContext") -> dict:
    """M2出力（LawContext）を UI表示用 dict にシリアライズする。

    Args:
        law_context: M2エージェントが生成した適用法令コンテキスト

    Returns:
        {
          "total_entries": 49,
          "categories": {"banking": 12, "human_capital": 8, ...},
          "warnings": ["重要カテゴリ0件: ..."],
          "entries": [
            {"law_id": "...", "title": "...", "category": "...",
             "source_confirmed": true/false},
            ...
          ]
        }
    """
    categories: dict[str, int] = {}
    for entry in law_context.applicable_entries:
        categories[entry.category] = categories.get(entry.category, 0) + 1

    return {
        "total_entries": len(law_context.applicable_entries),
        "categories": categories,
        "warnings": list(law_context.warnings),
        "entries": [
            {
                "law_id": e.id,
                "title": e.title,
                "category": e.category,
                "source_confirmed": e.source_confirmed,
            }
            for e in law_context.applicable_entries
        ],
    }


def serialize_m3(gap_result: "GapAnalysisResult") -> dict:
    """M3出力（GapAnalysisResult）を UI表示用 dict にシリアライズする。

    Args:
        gap_result: M3エージェントが生成したギャップ分析結果

    Returns:
        {
          "total_gaps": 130,
          "by_change_type": {"追加必須": 74, "修正推奨": 39, "参考": 17},
          "gaps": [
            {"gap_id": "...", "section": "...", "change_type": "...",
             "has_gap": true, "confidence": "高",
             "description": "...(先頭100文字)"},
            ...
          ]
        }
    """
    return {
        "total_gaps": gap_result.summary.total_gaps,
        "by_change_type": dict(gap_result.summary.by_change_type),
        "gaps": [
            {
                "gap_id": g.gap_id,
                "section": g.section_heading,
                "change_type": g.change_type,
                "has_gap": g.has_gap,
                "confidence": g.confidence,
                "description": (g.gap_description or "")[:100],
            }
            for g in gap_result.gaps
        ],
    }


def _proposal_quality_status(proposal_set: "ProposalSet") -> str:
    """3水準（松竹梅）の status から総合品質ステータスを返す。

    Returns:
        "fail": いずれかが "fail"
        "warn": いずれかが "warn"（fail なし）
        "pass": 全て "pass"
    """
    statuses = [proposal_set.matsu.status, proposal_set.take.status, proposal_set.ume.status]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def serialize_m4(proposals: "list[ProposalSet]") -> dict:
    """M4出力（list[ProposalSet]）を UI表示用 dict にシリアライズする。

    Args:
        proposals: M4エージェントが生成した提案セットのリスト

    Returns:
        {
          "total_proposals": 130,
          "proposals": [
            {"gap_id": "...", "disclosure_item": "...",
             "matsu_preview": "...(先頭80文字)",
             "take_preview": "...(先頭80文字)",
             "ume_preview": "...(先頭80文字)",
             "quality_status": "pass/warn/fail"},
            ...
          ]
        }
    """
    return {
        "total_proposals": len(proposals),
        "proposals": [
            {
                "gap_id": ps.gap_id,
                "disclosure_item": ps.disclosure_item,
                "matsu_preview": ps.matsu.text[:80],
                "take_preview": ps.take.text[:80],
                "ume_preview": ps.ume.text[:80],
                "quality_status": _proposal_quality_status(ps),
            }
            for ps in proposals
        ],
    }


def serialize_m5(report_md: str) -> dict:
    """M5出力（Markdownレポート文字列）を UI表示用 dict にシリアライズする。

    Args:
        report_md: M5エージェントが生成した Markdown レポート全文

    Returns:
        {
          "total_chars": 81808,
          "total_lines": 2466,
          "preview": "...(先頭1000文字)",
          "full_text": "...(全文)"
        }
    """
    return {
        "total_chars": len(report_md),
        "total_lines": report_md.count("\n") + 1 if report_md else 0,
        "preview": report_md[:1000],
        "full_text": report_md,
    }
