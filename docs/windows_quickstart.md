# Windows 操作手順書 — disclosure-multiagent

**作成日**: 2026-03-15
**作成者**: Majiro-ns
**対象環境**: Windows 11 + WSL2 (Ubuntu)

---

## 前提条件

以下がインストール済みであることを確認してください。

| 必要なもの | 確認コマンド | 最低バージョン |
|-----------|------------|--------------|
| WSL2 | `wsl --version` | 2.x |
| Python (WSL内) | `python3 --version` | 3.10+ |
| Node.js (WSL内) | `node --version` | 18.x+ |
| npm (WSL内) | `npm --version` | 9.x+ |

**WSL2 が未インストールの場合**: PowerShell（管理者）で `wsl --install` を実行後、再起動。

---

## 方法1: start_disclosure.bat（推奨）

Windowsエクスプローラーまたはダブルクリックで起動できるバッチファイルです。

### 場所

```
C:\path\to\disclosure-multiagent\start_disclosure.bat
```

### 手順

1. エクスプローラーで上記フォルダを開く
2. `start_disclosure.bat` をダブルクリック
3. 2つのコマンドプロンプトウィンドウが開く
   - 「disclosure-backend」: FastAPI (port 8010)
   - 「disclosure-frontend」: Next.js (port 3000)
4. 約5秒待ってからブラウザで `http://localhost:3000` を開く

### 動作内容（内部処理）

```
[0/2] 既存プロセス停止 (uvicorn + next dev)
[1/2] バックエンド起動
      WSL: PYTHONPATH=scripts:. uvicorn api.main:app --port 8010
[2/2] フロントエンド起動
      WSL: npx next dev --turbopack --hostname 0.0.0.0 --port 3000
```

### 確認方法

```powershell
# PowerShellで確認
# バックエンドが起動しているか
curl http://localhost:8010/health

# フロントエンドが起動しているか
curl http://localhost:3000
```

---

## 方法2: PowerShell から手動起動

バッチファイルが使えない場合や、ログをリアルタイムで確認したい場合。

### ターミナル1: バックエンド起動

```powershell
# PowerShell を開く
wsl bash -c "cd /path/to/disclosure-multiagent && PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8010"
```

### ターミナル2: フロントエンド起動

```powershell
# 別のPowerShellウィンドウを開く
wsl bash -c "cd /path/to/disclosure-multiagent/web && npx next dev --turbopack --hostname 0.0.0.0 --port 3000"
```

### ブラウザで確認

- UI: `http://localhost:3000`
- APIドキュメント: `http://localhost:8010/docs`
- APIヘルスチェック: `http://localhost:8010/health`
- サンプル分析結果: `http://localhost:3000/sample`

---

## 方法3: WSL ターミナルから直接起動

WSL2のUbuntuターミナルを使う場合。

```bash
# WSL2 ターミナルを開く
cd /path/to/disclosure-multiagent

# バックエンド（バックグラウンド実行）
PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8010 &

# 3秒待つ
sleep 3

# フロントエンド
cd web && npx next dev --turbopack --hostname 0.0.0.0 --port 3000
```

---

## 依存関係インストール（初回のみ）

初回実行時またはアップデート後に必要です。

### バックエンド（Python）

```bash
# WSL2 ターミナルで実行
cd /path/to/disclosure-multiagent

# 仮想環境の作成（推奨）
python3 -m venv .venv
source .venv/bin/activate

# 依存関係インストール
pip install -r api/requirements.txt

# または pip install -e ".[api,llm]"
```

**インストールされるパッケージ**:

| パッケージ | 用途 |
|-----------|------|
| fastapi, uvicorn | Web APIサーバー |
| pdfplumber, pymupdf | PDF解析 |
| anthropic | Claude API（M3/M4エージェント） |
| pyyaml | 法令YAMLの読み込み |
| python-docx, openpyxl | Word/Excel出力（M9） |

### フロントエンド（Node.js）

```bash
# WSL2 ターミナルで実行
cd /path/to/disclosure-multiagent/web

npm install
```

**確認**:
```bash
npm run build 2>&1 | tail -5   # ビルドエラーがないか確認
```

---

## 停止方法

### start_disclosure.bat 経由で起動した場合

- 「disclosure-backend」ウィンドウを閉じる（Ctrl+C後にウィンドウ閉じる）
- 「disclosure-frontend」ウィンドウを閉じる（Ctrl+C後にウィンドウ閉じる）

または PowerShell から一括停止:

```powershell
wsl bash -c "pkill -f 'uvicorn api.main' 2>/dev/null; pkill -f 'next dev' 2>/dev/null"
```

---

## よくあるエラーと対処法

### エラー1: `Internal Server Error` (APIエラー)

**症状**: フロントエンドで分析を実行すると 500 エラーが返る

**原因と対処**:
```bash
# バックエンドのログを確認
wsl bash -c "cd /path/to/disclosure-multiagent && PYTHONPATH=scripts:. python3 -m uvicorn api.main:app --port 8010 2>&1" | head -20
```

よくある原因:
- `PYTHONPATH` が正しく設定されていない → `PYTHONPATH=scripts:.` を確認
- 依存関係が未インストール → `pip install -r api/requirements.txt`
- ANTHROPIC_API_KEY が未設定（モックモードでは不要）

### エラー2: `ModuleNotFoundError`

**症状**: バックエンド起動時に `ModuleNotFoundError: No module named 'xxx'` が表示される

**対処**:
```bash
# 依存関係を再インストール
cd /path/to/disclosure-multiagent
pip install -r api/requirements.txt
```

### エラー3: `Port 3000 already in use`

**症状**: フロントエンドが「Port 3000 is in use」と表示して起動しない

**対処**:
```bash
# WSL2 で使用中のプロセスを確認・停止
wsl bash -c "lsof -i :3000"
wsl bash -c "pkill -f 'next dev'"

# またはWindowsから停止
netstat -ano | findstr :3000
taskkill /PID <PID番号> /F
```

### エラー4: `Port 8010 already in use`

```bash
# WSL2 で停止
wsl bash -c "pkill -f 'uvicorn api.main'"
```

### エラー5: WSL2 が `wsl: command not found`

**症状**: `wsl` コマンドが認識されない

**対処**:
- PowerShell（管理者）で `wsl --install` を実行
- Windows 11 の場合は再起動後に再試行

### エラー6: `EACCES: permission denied` (npm)

**症状**: npm install が権限エラーで失敗する

**対処**:
```bash
# /mnt/c/ 配下でのnpm問題 → WSLホームディレクトリで実行
# または node_modules を削除して再インストール
cd /path/to/disclosure-multiagent/web
rm -rf node_modules package-lock.json
npm install
```

### エラー7: モックモードで動作確認したい（ANTHROPIC_API_KEY不要）

API キーなしでも動作確認できます:

```bash
# ブラウザで /sample にアクセス
http://localhost:3000/sample

# または CLI でサンプルPDFを使う
wsl bash -c "cd /path/to/disclosure-multiagent && python3 -m scripts.app tests/fixtures/sample_yuho.pdf --mock"
```

---

## 環境変数（オプション）

実際の Claude API を使う場合は `.env` ファイルを設定してください。

```bash
# disclosure-multiagent/ 直下に .env を作成
# (WSL2で)
cat > /path/to/disclosure-multiagent/.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
EOF
```

**注意**: `.env` ファイルは `.gitignore` に含まれているため、commit されません。

---

## アクセスURL一覧

| URL | 説明 |
|-----|------|
| `http://localhost:3000` | メインUI（有報PDF分析） |
| `http://localhost:3000/sample` | サンプルデータで即確認 |
| `http://localhost:8010/docs` | FastAPI Swagger UI（API仕様） |
| `http://localhost:8010/health` | バックエンドヘルスチェック |

---

## ファイル構成（参考）

```
disclosure-multiagent/
├── start_disclosure.bat          # ← Windows一発起動スクリプト
├── api/
│   ├── main.py                   # FastAPIメインアプリ
│   └── requirements.txt          # Pythonパッケージ一覧
├── scripts/
│   ├── m1_pdf_agent.py           # PDF解析エージェント
│   ├── m2_law_agent.py           # 法令照合エージェント
│   ├── m3_gap_analysis_agent.py  # ギャップ分析
│   ├── m4_proposal_agent.py      # 松竹梅提案生成
│   └── m5_report_agent.py        # レポート生成
├── laws/                         # 法令YAMLファイル群
├── web/                          # Next.js フロントエンド
│   ├── src/
│   └── package.json
└── tests/
    └── fixtures/
        └── sample_yuho.pdf       # テスト用サンプル有報
```

---

*作成: 2026-03-15 / Majiro-ns*
