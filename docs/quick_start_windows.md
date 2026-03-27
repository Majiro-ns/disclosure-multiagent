# disclosure-multiagent クイックスタート（Windows 殿向け）

**作成日**: 2026-03-17
**対象**: 殿（上様）の日常操作用 — 最短3操作で起動

---

## ▶ 最速起動（推奨）

### エクスプローラーでダブルクリック

```
C:\path\to\disclosure-multiagent\start_disclosure.bat
```

1. `start_disclosure.bat` をダブルクリック
2. 2つのウィンドウが開く（backend / frontend）
3. ブラウザで **http://localhost:3000** を開く

完了。

---

## ▶ 手動起動（PowerShell 3コマンド）

PowerShell を **2枚** 開く。

### [1枚目] バックエンド起動

```powershell
wsl bash -c "cd /path/to/disclosure-multiagent && PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8010"
```

### [2枚目] フロントエンド起動

```powershell
wsl bash -c "cd /path/to/disclosure-multiagent/web && npx next dev --turbopack --hostname 0.0.0.0 --port 3000"
```

### [ブラウザ] 開く

```
http://localhost:3000
```

---

## ▶ サンプルPDFで動作確認

1. `http://localhost:3000` を開く
2. 「ファイルを選択」をクリック
3. 以下のサンプルファイルを選択：

```
C:\path\to\disclosure-multiagent\samples\sample_yuho.pdf
```

4. 「分析開始」ボタンをクリック

> APIキー不要（モックLLMモードで動作）

---

## ▶ ステップ実行モード（5段階進捗確認）

分析開始後、画面に5つのステップが順番に表示される：

```
[ M1: PDF読取     ] ✅ 完了 — 18セクション検出
[ M2: 法令確認    ] ✅ 完了 — 57件の法令エントリ
[ M3: ギャップ分析 ] 🔄 実行中...
[ M4: 改善提案    ]    待機中
[ M5: レポート生成 ]    待機中
```

各ステップが完了するたびにリアルタイムで更新される（SSE）。

### 各ステップの見方

| ステップ | 完了表示 | 正常範囲 |
|---------|---------|---------|
| M1: PDF読取 | 「N セクション検出」 | 10〜20件 |
| M2: 法令確認 | 「N 件の法令エントリ」 | 50〜90件 |
| M3: ギャップ分析 | 「ギャップ N 件検出」 | 1〜30件 |
| M4: 改善提案 | 「N 件の提案セット」 | ギャップ数と同数 |
| M5: レポート生成 | 「N 文字のレポート」 | 3000〜10000字 |

### Debug Mode（足軽が LLM を代替）

詳細設定で「**Debug Mode (Claude Code)**」を ON にすると、M3・M4 の LLM 呼び出しを足軽が代替する。
手順 → [debug_mode.md](./debug_mode.md)

---

## ▶ URL 一覧

| URL | 説明 |
|-----|------|
| `http://localhost:3000` | メインUI |
| `http://localhost:3000/sample` | サンプルデータ即確認 |
| `http://localhost:8010/docs` | API仕様（Swagger UI） |
| `http://localhost:8010/health` | バックエンド死活確認 |

---

## ▶ 停止方法

各ウィンドウで `Ctrl+C` → ウィンドウを閉じる。

または PowerShell から一括停止：

```powershell
wsl bash -c "pkill -f 'uvicorn api.main' 2>/dev/null; pkill -f 'next dev' 2>/dev/null"
```

---

## ▶ よくある問題

| 症状 | 対処 |
|------|------|
| `http://localhost:3000` が開かない | 30秒待ってからリロード |
| 分析が500エラー | バックエンドウィンドウのログを確認 |
| `Port already in use` | 一括停止コマンドを実行してから再起動 |
| 分析が遅い（Mock OFF 時） | `USE_MOCK_LLM=true` で実行 or Debug Mode |

詳細手順 → [windows_quickstart.md](./windows_quickstart.md)

---

*作成: 2026-03-17 / Majiro-ns*
