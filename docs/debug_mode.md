# Debug Mode — Claude Code足軽による LLM 代替

> **対象読者**: disclosure-multiagent を Claude Code（足軽）と一緒に使う開発者・運用担当者。
> APIキーなしで M3（ギャップ分析）・M4（改善提案）を足軽が代替応答するモードです。

---

## 概要

通常モード（`use_mock=false`）では M3/M4 が Anthropic API を呼び出します。
**Debug Mode** では API キー不要で、ファイルベースIPC（`/tmp/disclosure_debug/`）経由で
Claude Code（足軽）が M3/M4 の代わりに応答します。

```
通常: PDF → M1 → M2 → M3 (API) → M4 (API) → M5 → レポート
Debug: PDF → M1 → M2 → M3 (足軽) → M4 (足軽) → M5 → レポート
```

---

## 使い方（殿向けクイックスタート）

### ① サーバー起動

```bash
cd disclosure-multiagent
PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --port 8010
```

Windows の場合は `start_disclosure.bat` をダブルクリックするだけです。

### ② 足軽が debug_monitor.py を実行

```bash
python3 scripts/debug_monitor.py --auto
```

`--auto` モード：リクエストを表示してポーズ。足軽がWrite ツールで直接 response ファイルを書き込みます。

インタラクティブモード（手入力）の場合は引数なしで起動：

```bash
python3 scripts/debug_monitor.py
```

### ③ Web UI から PDF をアップロード（Debug Mode チェック ON）

ブラウザで `http://localhost:3000` を開き、詳細設定内の **「Debug Mode (Claude Code)」** チェックボックスを ON にして有報 PDF をアップロードします。

または curl で直接リクエスト：

```bash
curl -X POST http://localhost:8010/api/analyze/upload \
  -F "file=@tests/fixtures/sample_yuho.pdf" \
  -F "use_debug=true" \
  -F "use_mock=false" \
  -F "company_name=株式会社テスト商事" \
  -F "fiscal_year=2025" \
  -F "level=竹"
```

### ④ 足軽が M3/M4 の応答を入力

`debug_monitor.py` の表示を見て、system_prompt + user_prompt に対する応答を入力します。

**M3 応答フォーマット（JSON）:**

```json
{
  "has_gap": true,
  "confidence": "high",
  "summary": "人的資本KPI（エンゲージメントスコア等）の開示が不足しています。",
  "evidence": "テキスト内に数値目標の記載なし。"
}
```

**M4 応答フォーマット（自由テキスト）:**

```
当社は、エンゲージメントサーベイを年1回実施し、スコアを開示しています。
2025年3月期のエンゲージメントスコアは72点（前期比+5点）です。
```

**自動モード**（`--auto`）の場合は、表示されたファイルパスに response JSON を書き込みます：

```json
// /tmp/disclosure_debug/response_{uuid}.json
{
  "id": "{uuid}",
  "content": "（上記フォーマットの応答テキスト）",
  "created_at": "2026-03-14T10:00:00"
}
```

### ⑤ Web UI にレポート表示

パイプラインが完走すると、Web UI にレポートが表示されます。

---

## ファイルベース IPC の仕組み

```
/tmp/disclosure_debug/
  request_{uuid}.json   ← パイプラインが書く（M3/M4 呼び出し時）
  response_{uuid}.json  ← 足軽が書く（応答）
```

### request JSON スキーマ

```json
{
  "id": "uuid",
  "stage": "m3" | "m4",
  "system_prompt": "（LLMへのシステムプロンプト）",
  "user_prompt": "（分析対象テキスト・プロンプト）",
  "created_at": "2026-03-14T10:00:00+09:00"
}
```

### response JSON スキーマ

```json
{
  "id": "uuid（request と同じ）",
  "content": "（応答テキスト）",
  "created_at": "2026-03-14T10:00:00"
}
```

> **注意**: `content` キーが必須です（`response` ではありません）。

---

## タイムアウト

デフォルトのタイムアウトは **300秒（5分）** です。
`debug_ipc.py` の `DEFAULT_TIMEOUT` を変更すれば延長できます。

タイムアウト時は自動的にモック応答にフォールバックします。

---

## 実装ファイル

| ファイル | 役割 |
|---|---|
| `scripts/debug_ipc.py` | ファイルベースIPC ユーティリティ（単件: `write_request` / `wait_for_response` / `call_debug_llm`、バッチ: `write_batch_request` / `wait_for_batch_response` / `call_debug_llm_batch`） |
| `scripts/debug_monitor.py` | リクエスト監視モニター（インタラクティブ / 自動モード、バッチ対応） |
| `scripts/debug_prompts.py` | 足軽向け追加コンテキスト（M3/M4として振る舞うためのガイド） |
| `scripts/test_debug_mode.py` | TC-1〜TC-20 ユニットテスト（21件全PASS） |
| `scripts/test_step_debug_e2e.py` | ST-1〜ST-8 E2Eテスト（9件全PASS） |
| `api/routers/analyze.py` | `/api/analyze/upload` に `use_debug: bool = Form(False)` 追加 |
| `api/services/pipeline.py` | `run_pipeline_async()` に `use_debug` パラメータ追加 |

---

## バッチ IPC フォーマット

M3・M4 はバッチ IPC を使用して、130件以上の分析を **2回のIPC** で完結させます。

### バッチ request_{id}.json スキーマ

```json
{
  "id": "uuid",
  "stage": "m3",
  "batch": true,
  "item_count": 130,
  "system_prompt": "（共通システムプロンプト）",
  "items": [
    {"index": 0, "user_prompt": "（セクション0のプロンプト）"},
    {"index": 1, "user_prompt": "（セクション1のプロンプト）"},
    ...
  ],
  "created_at": "2026-03-14T10:00:00+09:00"
}
```

### バッチ response_{id}.json スキーマ

```json
{
  "id": "uuid（request と同じ）",
  "results": [
    {"index": 0, "content": "（index 0への応答）"},
    {"index": 1, "content": "（index 1への応答）"},
    ...
  ],
  "created_at": "2026-03-14T10:00:00"
}
```

> **バッチタイムアウト**: デフォルト **600秒（10分）**（単件より長め）。

---

## E2E テスト確認済み（2026-03-14）

- M3 バッチ: 130件× 2ステージ → 2回のIPCで完結
- debug mode 21テスト（TC-1〜TC-20）全PASS
- ST-1〜ST-8 E2Eテスト（単件/バッチ/タイムアウト/バックグラウンドスレッド）全PASS
- パイプライン全段階（USE_MOCK_LLM=true）: M1→M2→M3→M4→M5 完走 ✅
- レポート 89470文字生成

---

*作成者: Majiro-ns / 2026-03-14*
