# ステップ実行ガイド — 各段階の出力を確認しながら分析する

> **対象読者**: disclosure-multiagent を日常的に使う利用者・開発者。
> パイプラインの各段階（M1〜M5）の出力をリアルタイムで確認する方法を説明します。

---

## ステップ実行モードとは

パイプラインが M1（PDF読取）→ M2（法令確認）→ M3（ギャップ分析）→ M4（改善提案）→ M5（レポート生成）の順に実行され、各段階の完了をリアルタイムで確認できるモードです。

各ステップが完了するたびに UI が更新されるため、何が検出されたか・どこで時間がかかっているかをリアルタイムで把握できます。

---

## 使い方

### ① サーバー起動

```bash
# バックエンド起動
cd disclosure-multiagent
PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --port 8010

# フロントエンド起動（別ターミナル）
cd disclosure-multiagent/web
npm run dev
```

Windows の場合は `start_disclosure.bat` をダブルクリックするだけです。

### ② `http://localhost:3000` を開く

トップページが開きます。

### ③ 有報 PDF をアップロード

PDF をドラッグ&ドロップ、または「ファイルを選択」でアップロードします。

### ④ 分析開始 → ステップ表示を確認

「分析開始」ボタンを押すと分析ページに遷移し、5ステップの進捗バーが表示されます。

```
[ M1: PDF読取     ] ✅ 完了 — 18セクション検出
[ M2: 法令確認    ] ✅ 完了 — 57件の法令エントリ
[ M3: ギャップ分析 ] 🔄 実行中...
[ M4: 改善提案    ]    待機中
[ M5: レポート生成 ]    待機中
```

各ステップが完了するたびに表示が更新されます（SSE / Server-Sent Events でリアルタイム反映）。

### ⑤ M1 出力を確認（PDF読取）

完了表示: **「N セクション検出」**

何が検出されたか（セクション数）を確認します。
- 正常: 10〜20 セクション程度
- 少ない: PDF が画像スキャンの場合は要確認（テキスト抽出不可）

### ⑥ M2 出力を確認（法令確認）

完了表示: **「N 件の法令エントリ」**

- 通常は 50〜60 件（全業種共通＋業種別法令）
- 件数が極端に少ない場合は `laws/` YAML の確認が必要

### ⑦ M3 出力を確認（ギャップ分析）

完了表示: **「ギャップ N 件検出」**

- 追加必須・修正推奨・参考の3種別でギャップを検出
- 0件: 全項目が充足済み（または Debug Mode で足軽が「has_gap:false」で応答）
- 多すぎる場合（100件超）: 法令 YAML の精査を推奨

### ⑧ M4 出力を確認（改善提案）

完了表示: **「N 件の提案セット」**

- 各ギャップに対して 松・竹・梅 3段階の記載文案を生成

### ⑨ M5 レポートを確認（レポート生成）

完了表示: **「N 文字のレポート」**

分析ページの「レポートを表示」ボタンでマークダウンレポートが表示されます。

---

## Debug Mode との併用

詳細設定で「**Debug Mode (Claude Code)**」チェックを ON にすると、M3・M4 の LLM 呼び出しを足軽（Claude Code）が代替します。

### 並行実行の流れ

```
利用者（殿）          足軽
    │                  │
    ├─PDF アップロード→│
    │                  ├─ python3 scripts/debug_monitor.py --auto 起動
    │                  │
    │  ←M3実行中←───  │  request_{uuid}.json を /tmp/disclosure_debug/ に作成
    │                  ├─ リクエスト内容を確認し response_{uuid}.json を書き込み
    │  M3完了→───────  │
    │  ←M4実行中←───  │  （同様に M4 も足軽が応答）
    │                  │
    │ M5 レポート表示  │
```

**足軽の操作手順:**

```bash
# ターミナルで監視スクリプトを起動
python3 scripts/debug_monitor.py --auto

# 出力例:
# ============================================================
# [10:00:05] 📩 リクエスト検知: request_abc123.json
#   ID: abc123...
# ============================================================
# --- SYSTEM PROMPT ---
# （M3のシステムプロンプト）
# --- USER PROMPT ---
# （分析対象テキスト）
#
# ⏸  応答待機中...
#    以下のファイルを作成してください:
#    /tmp/disclosure_debug/response_abc123.json
```

足軽は response JSON を作成して応答します（詳細 → [debug_mode.md](./debug_mode.md)）。

---

## 各段階の出力の読み方

### M2 WARNING への対応

```
重要カテゴリが0件: SSBJ
```

→ `laws/ssbj_2025.yaml` にエントリが存在しない年度への参照です。通常動作なので無視してください。

### M3 ギャップ一覧の確認ポイント

| 優先度 | change_type | 意味 | 対応 |
|--------|------------|------|------|
| 高 | 追加必須 | 法令上の追加義務 | 速やかに追記が必要 |
| 中 | 修正推奨 | 記載精度の改善 | 次回改訂時に対応 |
| 低 | 参考 | ベストプラクティス | 任意 |

### M4 提案文案の活用

生成された文案は **草案** です。以下を必ず確認してください：

1. 会社固有の数値（売上・従業員数・KPI 等）を実際の値に置換
2. 法令 URL の有効性を確認（`scripts/verify_law_urls.py` で検証可）
3. 外部専門家（弁護士・公認会計士）のレビューを経てから採用

---

## API で直接利用する場合

```bash
# 分析開始
curl -X POST http://localhost:8010/api/analyze/upload \
  -F "file=@your_report.pdf" \
  -F "company_name=株式会社例" \
  -F "level=竹" \
  -F "use_mock=false"

# レスポンス例: {"task_id":"abc123","status":"queued"}

# ステップ進捗をリアルタイムストリーム（SSE）
curl http://localhost:8010/api/status/abc123/stream

# または、完了後にステータスを一括取得
curl http://localhost:8010/api/status/abc123
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| M1 で「0 セクション検出」 | PDF が画像スキャン / 暗号化 | テキスト付き PDF を使用 |
| M2 で法令件数が少ない | `laws/` YAML の記述不足 | YAML を確認・追加 |
| M3 が長時間「実行中」 | LLM API 応答待ち（Mock OFF 時） | `use_mock=true` で試す、または Debug Mode |
| M3 で「ギャップ 0 件」 | 全項目充足 / Debug Mode で全て has_gap:false | 意図通りか確認 |
| レポートに `[セクション名]` が残る | M4 のプレースホルダ | 手動で実際の値に置換 |

---

## 中間出力シリアライザ（step_serializers.py）

各ステップの出力は `scripts/step_serializers.py` で UI 表示用 dict に変換されます。

| 関数 | 入力型 | 主要フィールド |
|------|--------|----------------|
| `serialize_m1(report)` | `StructuredReport` | `total_sections`, `sections[]` |
| `serialize_m2(law_context)` | `LawContext` | `total_entries`, `categories`, `warnings` |
| `serialize_m3(gap_result)` | `GapAnalysisResult` | `total_gaps`, `by_change_type`, `gaps[]` |
| `serialize_m4(proposals)` | `list[ProposalSet]` | `total_proposals`, `proposals[]`, `quality_status` |
| `serialize_m5(report_md)` | `str` | `total_chars`, `total_lines`, `preview`, `full_text` |

## 関連ドキュメント

- [debug_mode.md](./debug_mode.md) — Debug Mode（足軽が LLM を代替）の詳細手順

---

*作成者: Majiro-ns / 2026-03-14*
