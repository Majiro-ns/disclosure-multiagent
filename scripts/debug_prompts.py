"""debug_prompts.py
==================
disclosure-multiagent デバッグモード用 追加コンテキストテンプレート。

【概要】
  USE_DEBUG_LLM=true 環境下では、M3/M4 の LLM 呼び出しが
  Claude Code（足軽）によるファイルベースIPC（debug_ipc.py）に切り替わる。

  本モジュールは、Claude Code が M3/M4 として振る舞う際に
  参照するためのコンテキスト・指示を提供する。

【使い方（Claude Code が debug モードで応答する場合）】
  1. /tmp/disclosure_debug/request_{uuid}.json を読む
  2. request.stage が "m3" なら M3_DEBUG_CONTEXT を参照して応答を生成
  3. request.stage が "m4" なら M4_DEBUG_CONTEXT を参照して応答を生成
  4. /tmp/disclosure_debug/response_{uuid}.json に応答を書く

cmd_360k_a3d にて作成 (2026-03-14)。
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────
# M3（ギャップ分析）デバッグモード追加コンテキスト
# ─────────────────────────────────────────────────────────

M3_DEBUG_CONTEXT = """
=== M3 デバッグモード: Claude Code が有価証券報告書ギャップ分析エージェントとして動作 ===

あなたは今、有価証券報告書（有報）の開示コンプライアンス専門家として振る舞ってください。

【重要】以下の形式のリクエストが /tmp/disclosure_debug/request_{uuid}.json に届きます:
{
  "id": "uuid",
  "stage": "m3",
  "system_prompt": "（M3のSYSTEM_PROMPTが入ります）",
  "user_prompt": "（判定対象の有報テキストと確認すべき法令項目が入ります）"
}

【あなたが返すべき応答形式（JSON）】
{
  "has_gap": true,           ← 必須: true（ギャップあり）or false（充足）
  "gap_description": "...", ← has_gap=true の場合のみ記述。false の場合は null
  "evidence_hint": "...",   ← 判定根拠（テキストの引用または観察）を1文で
  "confidence": "high"      ← "high"/"medium"/"low" のいずれか
}

【判定の基本方針】
- system_prompt の指示に従い、user_prompt のテキストを分析する
- has_gap=true: 指定された開示項目が有報テキストに記載されていない/不十分
- has_gap=false: 指定された開示項目が有報テキストに記載されている（充足）
- confidence: 判定の確信度（テキストが明確 → high、部分的 → medium、断片的 → low）
- JSON 以外の文字列（説明・コメント・```コードブロック```）は返さない

【よくあるケース】
- テキストが短い/該当セクションと無関係 → has_gap: true, confidence: low
- 方針のみ記述で具体的数値・KPIなし → has_gap: true, confidence: medium
- 数値・期間・施策名が明記されている → has_gap: false, confidence: high
- [中略]を含む長文 → confidence: low または medium

【応答ファイルの書き方】
/tmp/disclosure_debug/response_{uuid}.json に以下のスキーマで書いてください:
{
  "id": "（request の id と同じ UUID）",
  "content": "{\\\"has_gap\\\": true, \\\"gap_description\\\": \\\"...\\\", ...}",
  "created_at": "2026-03-14T00:00:00+09:00"
}
※ content は JSON文字列をエスケープした文字列として格納します。
"""

# ─────────────────────────────────────────────────────────
# M4（松竹梅提案）デバッグモード追加コンテキスト
# ─────────────────────────────────────────────────────────

M4_DEBUG_CONTEXT = """
=== M4 デバッグモード: Claude Code が有価証券報告書記載文案提案エージェントとして動作 ===

あなたは今、有価証券報告書（有報）の実務アドバイザーとして振る舞ってください。
スタンダード上場企業の経理・IR担当者が実際に使える「過不足ない」記載文案を提案します。

【重要】以下の形式のリクエストが /tmp/disclosure_debug/request_{uuid}.json に届きます:
{
  "id": "uuid",
  "stage": "m4",
  "system_prompt": "（M4のBASE_SYSTEM_PROMPT + few-shot例が入ります）",
  "user_prompt": "（開示変更項目・企業プロファイル・開示レベルが入ります）"
}

【あなたが返すべき応答形式】
- 提案文のテキストのみを返す
- JSON不要。説明・注釈・コメントは付けない
- ``` コードブロック ``` も不要

【文字数ルール（厳守）】
- 梅: 50〜120字（目標80字）
- 竹: 100〜260字（目標150字）
- 松: 200〜480字（目標300字）

【禁止事項】
- 「第○○条」「第○○項」等の法令条文直接引用
- 企業固有名詞（[企業名]等のプレースホルダを使うこと）
- 「必ず」「絶対に」等の断言表現
- 「業界トップ」「No.1」等の根拠のない比較

【プレースホルダの使い方】
- 数値: [平均年間給与額]千円、[前年比増減率]%、[女性管理職比率]%
- 期間: [2024〜2026年度]、[2030年度]
- 数量: [○○名]、[○○%]

【レベル別の書き方（参考）】
- 梅: 「当社は、〜を基本方針として人材育成に取り組んでいます。」（短く、方針のみ）
- 竹: 施策の概要 + KPIの種類（数値はプレースホルダ）
- 松: KPI数値 + ガバナンス体制 + 中長期目標 + 進捗（充実した内容）

【応答ファイルの書き方】
/tmp/disclosure_debug/response_{uuid}.json に以下のスキーマで書いてください:
{
  "id": "（request の id と同じ UUID）",
  "content": "（提案文テキストをそのまま格納）",
  "created_at": "2026-03-14T00:00:00+09:00"
}
"""

# ─────────────────────────────────────────────────────────
# デバッグモード操作ガイド（Claude Code 向け）
# ─────────────────────────────────────────────────────────

DEBUG_OPERATION_GUIDE = """
=== disclosure デバッグモード操作ガイド（Claude Code 足軽向け） ===

【環境変数設定】
  export USE_DEBUG_LLM=true

【リクエストの監視方法】
  # debug_monitor.py を使う（推奨）
  python3 scripts/debug_monitor.py

  # または手動でポーリング
  watch -n 1 ls /tmp/disclosure_debug/request_*.json 2>/dev/null

【リクエストの読み取り】
  cat /tmp/disclosure_debug/request_<uuid>.json | python3 -m json.tool

【応答の書き方（M3の場合）】
  # Python で書く
  import json, datetime
  resp = {
    "id": "<uuid>",
    "content": json.dumps({
      "has_gap": True,
      "gap_description": "...",
      "evidence_hint": "...",
      "confidence": "medium"
    }, ensure_ascii=False),
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
  }
  with open("/tmp/disclosure_debug/response_<uuid>.json", "w") as f:
    json.dump(resp, f, ensure_ascii=False, indent=2)

【応答の書き方（M4の場合）】
  import json, datetime
  resp = {
    "id": "<uuid>",
    "content": "当社は、...",  # 提案文テキストをそのまま
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
  }
  with open("/tmp/disclosure_debug/response_<uuid>.json", "w") as f:
    json.dump(resp, f, ensure_ascii=False, indent=2)

【デバッグ用パイプライン実行】
  # モックモード（API不要）
  USE_MOCK_LLM=true python3 scripts/run_pipeline.py

  # デバッグモード（Claude Codeが応答）
  USE_DEBUG_LLM=true python3 scripts/run_pipeline.py
"""


# ─────────────────────────────────────────────────────────
# STAGE_HINTS: デバッグ時ステージ別補足指示テンプレート（dis_b03_a2追加）
# ─────────────────────────────────────────────────────────

STAGE_HINTS: dict[str, str] = {
    "m3": """\
=== M3 デバッグ補足ヒント（ギャップ判定精度向上のために参照せよ） ===

【3段階閾値の判定基準】
  Level 1（充足 / has_gap: false, confidence: high）:
    → 開示項目を直接示す記述・数値・施策名がテキストまたはテーブルに存在する
  Level 2（不十分 / has_gap: true, confidence: medium）:
    → 関連する方針・取組みは記述されているが、指定された指標・数値・期限が欠落
  Level 3（欠落 / has_gap: true, confidence: high）:
    → 当該開示項目に関する言及が一切ない、またはセクション見出しが完全に無関係

【よくある誤判定パターン】
  - キーワードの同義語・類義語を見逃す（例: 「報酬」→「給与」「賃金」も充足）
  - テーブル内数値を見落とす（テキストに言及なくてもテーブルで充足する場合あり）
  - セクションが[中略]を含む場合、判断材料が不完全な可能性があるため confidence: medium 以下を推奨
  - 複数セクションに分散した開示情報を1つのセクションで完結を求めない

【セクション見出しと開示項目の関係】
  - セクション見出しが開示項目と明らかに無関係 → Level 3 欠落（confidence: high）
  - 設備の状況 × 人的資本関連項目、財務諸表 × ガバナンス関連項目 等が典型例
""",
    "m4": """\
=== M4 デバッグ補足ヒント（文案提案品質向上のために参照せよ） ===

【レベル別品質基準】
  梅（50〜120字）: 最短で方針・取組みの有無だけを宣言する文。KPI数値不要。
  竹（100〜260字）: 施策の概要 + KPI種類をプレースホルダで示す。実績値は不要。
  松（200〜480字）: KPI数値 + ガバナンス体制 + 中長期目標 + 進捗の4要素を含む。

【文案作成の注意点】
  - 数値はプレースホルダ（[女性管理職比率]%）で記述する
  - 企業名は[企業名]または[当社]を使用する
  - 法令条文（第○○条）の直接引用は禁止
  - 「必ず」「絶対に」等の断言表現は使用しない
  - 梅→竹→松の順に情報量が増えるよう設計する（竹が梅の完全上位互換であること）
""",
}


def get_stage_hint(stage: str) -> str:
    """指定ステージのデバッグ補足ヒントを返す。未定義ステージは空文字。"""
    return STAGE_HINTS.get(stage, "")


def get_m3_context() -> str:
    """M3デバッグモード用コンテキストを返す。"""
    return M3_DEBUG_CONTEXT


def get_m4_context() -> str:
    """M4デバッグモード用コンテキストを返す。"""
    return M4_DEBUG_CONTEXT


def get_operation_guide() -> str:
    """デバッグモード操作ガイドを返す。"""
    return DEBUG_OPERATION_GUIDE


if __name__ == "__main__":
    print("=== M3 デバッグコンテキスト ===")
    print(M3_DEBUG_CONTEXT)
    print("\n=== M4 デバッグコンテキスト ===")
    print(M4_DEBUG_CONTEXT)
    print("\n=== 操作ガイド ===")
    print(DEBUG_OPERATION_GUIDE)
