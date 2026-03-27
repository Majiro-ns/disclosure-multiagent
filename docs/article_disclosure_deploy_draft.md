---
title: "有報分析AIを本番環境にデプロイする — FastAPI+Docker実装"
emoji: "🚀"
type: "tech"
topics: ["python", "fastapi", "docker", "ai", "api"]
published: false
---

## はじめに

前回までの記事では、有価証券報告書（有報）を自動分析するパイプライン（M1〜M9）の実装を紹介してきた。PDFの解析・法令照合・ギャップ分析・提言生成と、各モジュールが揃ったところで次の問いが生まれる。

**本番で使えるようにするには、どうすればいいか。**

CLIツールとして動かせても、それだけでは実務投入できない。チームメンバーがWebブラウザから有報を投入し、分析結果をリアルタイムで確認できる形が必要だ。本記事では、M1〜M5パイプラインをFastAPIでラップし、Dockerコンテナ化して本番デプロイするまでの全工程を解説する。

実装はすべて OSS として公開している。
https://github.com/Majiro-ns/disclosure-multiagent

実装の要点はこうだ。

- **FastAPI + APIRouter**: 7つの責務を明確に分離したルーター設計
- **非同期パイプライン**: BackgroundTasks + `run_in_executor` でブロッキング処理を安全に切り離す
- **SSE（Server-Sent Events）**: 長時間実行の分析進捗をリアルタイムストリーム配信
- **Docker Compose**: backend（Python/FastAPI）+ web（Next.js）の2サービス構成
- **段階的な認証設計**: 開発中は認証スキップ、本番では API Key 有効化

---

## アーキテクチャ全体像

```
┌─────────────────────────────────────────────────────────┐
│                    クライアント                          │
│  ブラウザ / curl / Next.js Web UI                        │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP / SSE
                        ▼
┌─────────────────────────────────────────────────────────┐
│            FastAPI アプリケーション (port 8010)          │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ /analyze │  │ /edinet  │  │ /status  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│  ┌──────────┐  ┌──────────────────────┐               │
│  │/checklist│  │    /scoring          │               │
│  └──────────┘  └──────────────────────┘               │
│                                                         │
│  ┌─────────────────────────────────────────┐           │
│  │   services/ (pipeline, edinet, scoring) │           │
│  └───────────────┬─────────────────────────┘           │
└──────────────────┼─────────────────────────────────────┘
                   │ 直接呼び出し
                   ▼
┌──────────────────────────────────────────────────────────┐
│  scripts/ (M1〜M9 パイプライン実装)                       │
│  m1_pdf_agent.py / m3_gap_analysis_agent.py / ...        │
└──────────────────────────────────────────────────────────┘
```

FastAPIレイヤーはラッパーに徹し、ビジネスロジックはすべて `scripts/` 配下の既存モジュールに委譲している。この設計により、CLI経由でのデバッグとAPI経由での本番利用を両立できる。

---

## FastAPI アプリケーション設計

### main.py — 7ルーターの接続

`api/main.py` でFastAPIインスタンスを生成し、7つのルーターをマウントする。

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analyze, edinet, status, checklist, checklist_eval, checklist_stats, scoring

app = FastAPI(
    title="Disclosure Multiagent API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(edinet.router)
app.include_router(analyze.router)
app.include_router(status.router)
app.include_router(checklist.router)
app.include_router(checklist_eval.router)
app.include_router(checklist_stats.router)
app.include_router(scoring.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "disclosure-multiagent"}
```

各ルーターは `prefix` と `tags` を自前で宣言するため、`main.py` はルーターを繋ぐだけでよい。`/api/health` は Docker のヘルスチェックから叩かれるシンプルな死活確認エンドポイントだ。

### ルーター責務の分離

| ルーター | prefix | 主な責務 |
|---|---|---|
| `analyze` | `/api` | PDF分析パイプライン実行 |
| `edinet` | `/api/edinet` | EDINET企業検索・書類DL |
| `status` | `/api` | タスク状態確認・SSEストリーム |
| `checklist` | `/api/checklist` | 開示チェックリスト照合 |
| `checklist_eval` | `/api/checklist_eval` | チェックリスト評価 |
| `checklist_stats` | `/api/checklist_stats` | 統計・集計 |
| `scoring` | `/api/scoring` | 変更インパクトスコアリング |

---

## 認証設計 — 段階的な API Key 管理

本番APIを無認証で公開するのは論外だが、開発中に毎回トークンを設定するのも煩雑だ。`api/auth.py` はこの矛盾を環境変数の有無で解決している。

```python
import os
from fastapi import Header, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_API_KEY = os.environ.get("API_KEY", "")
_bearer = HTTPBearer(auto_error=False)


async def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> None:
    """API Key を検証する。API_KEY 未設定時は開発モードとしてスキップ。"""
    if not _API_KEY:
        return  # 開発モード: 認証スキップ

    token = x_api_key or (credentials.credentials if credentials else None)
    if token != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

`API_KEY` 環境変数が空のとき、`verify_api_key` は即座に `return` する。本番では `API_KEY=your-secret` を設定するだけで認証が有効になる。呼び出し側では `X-API-Key` ヘッダー、または `Authorization: Bearer <token>` のどちらでも渡せる。

ルーターへの適用は `Depends` で一行だ。

```python
@router.get("/edinet/search")
async def search_company(
    name: str = Query(...),
    _auth: None = Depends(verify_api_key),  # ← 認証依存性注入
):
    ...
```

---

## メインエンドポイント — 有報分析パイプライン

### JSON 投入

最もシンプルな使い方は、EDINET の書類管理番号を JSON で投入する方法だ。

```python
@router.post("/api/analyze")
async def analyze_document(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(verify_api_key),
) -> AnalyzeResponse:
    task_id = create_task()
    background_tasks.add_task(run_pipeline_async, task_id, request)
    return AnalyzeResponse(task_id=task_id, status="queued")
```

呼び出しはこうなる。

```bash
curl -X POST http://localhost:8010/api/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret" \
  -d '{"doc_id": "S100TRGP", "doc_type": "yuho"}'
```

レスポンスはすぐに返る。

```json
{"task_id": "a3f1b2c4", "status": "queued"}
```

### PDF直接アップロード

EDINET から直接 DL せず、手元の PDF を投入したい場合は `POST /api/analyze/upload` を使う。4段階のバリデーションで安全性を担保している。

```python
@router.post("/api/analyze/upload")
async def analyze_upload(
    file: UploadFile,
    doc_type: DocTypeCode = Form(DocTypeCode.yuho),
    background_tasks: BackgroundTasks = ...,
    _auth: None = Depends(verify_api_key),
) -> AnalyzeResponse:
    # バリデーション 1: 拡張子
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "PDF ファイルのみ受け付けます")

    # バリデーション 2: Content-Type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, "Unsupported Media Type")

    content = await file.read()

    # バリデーション 3: ファイルサイズ（20MB上限）
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "ファイルサイズが 20MB を超えています")

    # バリデーション 4: マジックバイト（%PDF）
    if not content.startswith(b"%PDF"):
        raise HTTPException(400, "PDF ファイルのマジックバイトが不正です")

    upload_dir = Path("/tmp/disclosure_uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / file.filename
    pdf_path.write_bytes(content)

    task_id = create_task()
    background_tasks.add_task(run_pipeline_async, task_id, request_from_path(pdf_path, doc_type))
    return AnalyzeResponse(task_id=task_id, status="queued")
```

拡張子・MIMEタイプ・サイズ・マジックバイトの4重チェックにより、悪意ある非PDFファイルの投入を防ぐ。

---

## 非同期パイプライン — ブロッキング処理の安全な切り離し

M1〜M5の処理は内部でLLM呼び出しやファイルI/Oが走るため、完了まで数十秒かかることがある。FastAPIのイベントループをブロックしないよう、`run_in_executor` を使って別スレッドで実行する。

```python
# api/services/pipeline.py

import asyncio
import uuid
from api.models.schemas import PipelineStatus

_tasks: dict[str, PipelineStatus] = {}  # インメモリタスクストア


def create_task() -> str:
    """UUID4 先頭8文字をタスクIDとして払い出す。"""
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = PipelineStatus(
        task_id=task_id,
        status="queued",
        progress=0,
        current_step="",
    )
    return task_id


async def run_pipeline_async(task_id: str, request: AnalyzeRequest) -> None:
    """M1-M5 パイプラインを非同期実行する。"""
    loop = asyncio.get_event_loop()

    def _run():
        # ブロッキング処理をスレッドプールで実行
        _update_task(task_id, status="running", progress=10, step="M1: PDF解析")
        m1_result = run_m1(request.doc_id or request.pdf_path)

        _update_task(task_id, progress=30, step="M2: 法令照合")
        m2_result = run_m2(m1_result)

        _update_task(task_id, progress=50, step="M3: ギャップ分析")
        m3_result = run_m3(m2_result)

        _update_task(task_id, progress=70, step="M4: 提言生成")
        m4_result = run_m4(m3_result)

        _update_task(task_id, progress=90, step="M5: レポート作成")
        m5_result = run_m5(m4_result)

        _update_task(task_id, status="done", progress=100, result=m5_result)

    try:
        await loop.run_in_executor(None, _run)
    except Exception as e:
        _update_task(task_id, status="error", error=str(e))
```

`loop.run_in_executor(None, ...)` は Python の標準スレッドプールを使う。M1〜M5 はすべて同期関数なので、GIL の影響を受けるが、I/Oバウンドな処理（PDF読み込み・HTTP呼び出し）の待機中は他のリクエストを処理できる。

---

## リアルタイム進捗配信 — Server-Sent Events

長時間かかる分析中の進捗状況（どのステップを実行中か）をクライアントにリアルタイムで伝えるため、SSEを使ったストリームエンドポイントを実装した。

```python
# api/routers/status.py

from sse_starlette.sse import EventSourceResponse

@router.get("/status/{task_id}/stream")
async def stream_status(task_id: str):
    """SSE でパイプライン進捗をリアルタイムストリーム配信."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")

    async def event_generator():
        last_state = ""
        while True:
            task = get_task(task_id)
            if not task:
                break

            current_state = json.dumps(task.model_dump(), ensure_ascii=False, default=str)
            if current_state != last_state:
                last_state = current_state
                yield {"event": "status", "data": current_state}

            if task.status in ("done", "error"):
                yield {"event": "complete", "data": current_state}
                break

            await asyncio.sleep(0.5)  # 0.5秒ポーリング

    return EventSourceResponse(event_generator())
```

ポーリング間隔は 0.5秒。状態変化があったときのみ `yield` するので、無駄な送信を抑えている。完了または失敗で `complete` イベントを送信してジェネレータを終了する。

クライアント側（JavaScript）での受信は `EventSource` で一行だ。

```javascript
const es = new EventSource(`/api/status/${taskId}/stream`);
es.addEventListener("status", (e) => {
  const data = JSON.parse(e.data);
  setProgress(data.progress);
  setCurrentStep(data.current_step);
});
es.addEventListener("complete", (e) => {
  const data = JSON.parse(e.data);
  setResult(data.result);
  es.close();
});
```

SSE は WebSocket と異なり、HTTP/1.1 で動作しサーバー→クライアントの一方向通信のみをサポートする。分析進捗の通知には十分であり、インフラ要件が軽い点で優れている。

---

## EDINET 連携エンドポイント

M7（m7_edinet_client.py）をそのまま `api/services/edinet_service.py` でラップし、RESTエンドポイントとして公開した。

```python
# api/routers/edinet.py（抜粋）

@router.get("/edinet/search", response_model=CompanySearchResponse)
async def search_company(
    name: str = Query(None, description="企業名（部分一致）"),
    sec_code: str = Query(None, description="証券コード（4桁）"),
    _auth: None = Depends(verify_api_key),
):
    """証券コード・企業名でEDINET登録企業を検索."""
    if sec_code:
        results = search_by_sec_code(sec_code)
    elif name:
        results = search_by_name(name)
    else:
        raise HTTPException(400, "sec_code または name が必要です")
    return CompanySearchResponse(results=results, total=len(results))


@router.get("/edinet/download/{doc_id}")
async def download_pdf(doc_id: str, _auth: None = Depends(verify_api_key)):
    """書類管理番号で有報PDFをダウンロード（認証不要の公開DL）."""
    pdf_path = download_document_pdf(doc_id)
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{doc_id}.pdf")
```

EDINET の PDF ダウンロードは認証不要の公開エンドポイントなので（M7記事参照）、`download_document_pdf` 内ではサブスクリプションキーなしで直接 DL できる。APIサーバー経由で DL することで、フロントエンドはクロスオリジン制約を気にせず有報 PDF を取得できる。

---

## スコアリングエンドポイント

開示文書の変更インパクトを 0〜100 の数値スコアで表す `POST /api/scoring/document` を実装した。

```python
# api/routers/scoring.py（抜粋）

@router.post("/document", response_model=ScoringResponse)
async def score_document(request: ScoringRequest) -> ScoringResponse:
    """開示文書テキストをPOSTし、変更インパクトスコアを返す。

    スコア構成:
    - checklist_coverage_score: チェックリスト一致率（0-100）
    - change_intensity_score: 変更語彙の濃度（0-100）
    - overall_risk_score: 総合リスクスコア（0-100）
    - risk_level: "low" (<40) / "medium" (40-69) / "high" (>=70)
    """
    result = scoring_service.score_document(request.disclosure_text)
    return ScoringResponse(**result)
```

`scoring_service.score_document()` の内部では、チェックリストキーワードのマッチ率と変更関連語彙（変更・修正・廃止 等）の出現密度を組み合わせてスコアを算出している。`risk_level` は `overall_risk_score` に基づいて自動判定される。

---

## Docker 化

### Dockerfile — シングルステージ構成

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 依存ライブラリのみ先にコピー（レイヤーキャッシュ最適化）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

EXPOSE 8010

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

`python:3.12-slim` を使い、不要なパッケージを省いてイメージサイズを最小化している。`requirements.txt` を先にコピーして `pip install` を先に実行することで、コードを変更してもライブラリ層のキャッシュが効くため、再ビルドが高速になる。

### docker-compose.yml — 2サービス構成

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: api/Dockerfile
    container_name: disclosure-backend
    ports:
      - "8010:8010"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - EDINET_SUBSCRIPTION_KEY=${EDINET_SUBSCRIPTION_KEY:-}
    volumes:
      - ./api/data:/app/api/data   # チェックリストデータの永続化
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8010/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: disclosure-web
    ports:
      - "3010:3010"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8010
    depends_on:
      backend:
        condition: service_healthy  # ← バックエンドのヘルスチェック通過後に起動
    restart: unless-stopped
```

重要な設計ポイントを3つ挙げる。

**① depends_on + condition: service_healthy**
Next.js の Web サービスは、バックエンドのヘルスチェックが通過してから起動する。単純な `depends_on` だとバックエンドが起動プロセスに入った直後に Web コンテナが立ち上がり、接続エラーが発生する。`condition: service_healthy` でこれを防ぐ。

**② NEXT_PUBLIC_API_URL=http://backend:8010**
コンテナ間通信は Docker の内部 DNS（サービス名）で解決する。ホスト側の `localhost:8010` ではなく、コンテナ名 `backend` でアクセスする。`NEXT_PUBLIC_` プレフィックスにより Next.js のブラウザ側コードにも同じ URL が使われるが、実際のブラウザからは `http://localhost:8010` にリクエストが飛ぶ。SSR とブラウザの両方で正しく動作させるには環境ごとに URL を切り替える考慮が必要だ（本実装では開発用途として同一ホストを想定）。

**③ volumes: ./api/data:/app/api/data**
チェックリストデータ（`checklist_data.json` 等）をホストにマウントすることで、コンテナを再ビルドせずにデータを更新できる。

---

## 起動手順

### 開発環境（認証なし）

```bash
# API キーなしで起動（開発モード: 認証スキップ）
cd /path/to/disclosure-multiagent
uvicorn api.main:app --reload --port 8010

# 動作確認
curl http://localhost:8010/api/health
# → {"status": "ok", "service": "disclosure-multiagent"}

# 有報分析（書類管理番号指定）
curl -X POST http://localhost:8010/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "S100TRGP", "doc_type": "yuho"}'
# → {"task_id": "a3f1b2c4", "status": "queued"}

# 進捗確認（ポーリング）
curl http://localhost:8010/api/status/a3f1b2c4

# 進捗確認（SSEストリーム）
curl -N http://localhost:8010/api/status/a3f1b2c4/stream
```

### 本番環境（Docker Compose）

```bash
# 環境変数を設定
export ANTHROPIC_API_KEY=sk-ant-xxxx
export EDINET_SUBSCRIPTION_KEY=your-edinet-key

# ビルド＆起動
docker-compose up -d --build

# ヘルスチェック確認
docker-compose ps

# ログ確認
docker-compose logs -f backend
```

### API Key 有効化

```bash
# .env ファイルに API_KEY を設定
echo "API_KEY=your-api-secret" >> .env

# 以降のリクエストには X-API-Key ヘッダーが必要
curl -X POST http://localhost:8010/api/analyze \
  -H "X-API-Key: your-api-secret" \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "S100TRGP", "doc_type": "yuho"}'
```

---

## Pydantic スキーマ設計

FastAPI の型安全性はすべて `api/models/schemas.py` の Pydantic モデルに支えられている。主要なスキーマを示す。

```python
from enum import Enum
from pydantic import BaseModel
from typing import Optional


class DocTypeCode(str, Enum):
    """書類種別コード."""
    yuho = "yuho"    # 有価証券報告書
    shoshu = "shoshu"  # 召集通知


class AnalyzeRequest(BaseModel):
    doc_id: Optional[str] = None      # EDINET書類管理番号
    doc_type: DocTypeCode = DocTypeCode.yuho
    use_mock: bool = False             # モック実行フラグ（テスト用）


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str


class PipelineStatus(BaseModel):
    task_id: str
    status: str           # "queued" / "running" / "done" / "error"
    progress: int         # 0〜100
    current_step: str     # "M1: PDF解析" 等
    result: Optional[dict] = None
    error: Optional[str] = None
```

`DocTypeCode` を `str, Enum` で定義することで、OpenAPI ドキュメントに選択肢が自動記載される。FastAPI の `/docs` を開くと、`yuho` / `shoshu` のドロップダウンがSwagger UI上に表示される。

---

## 今後の改善方針

### タスクストアの永続化

現状、`_tasks: dict[str, PipelineStatus]` はインメモリのため、コンテナ再起動で失われる。Redisへの移行が次のステップだ。

```python
# 現状（インメモリ）
_tasks: dict[str, PipelineStatus] = {}

# 改善案（Redis）
import redis
r = redis.Redis(host="redis", port=6379)

def get_task(task_id: str) -> PipelineStatus | None:
    data = r.get(f"task:{task_id}")
    return PipelineStatus.model_validate_json(data) if data else None
```

### ワーカーキューの導入

PDF分析は CPU/IO 集約的であるため、並列リクエストが増えると応答が遅くなる。Celery + Redis を使ったワーカーキューへの移行で、スケールアウトが可能になる。

```
クライアント → FastAPI → Redis キュー → Celery ワーカー（複数台）
```

### 認証の強化

現状の API Key は固定文字列だ。JWT + リフレッシュトークンへの移行、あるいは Cognito / Auth0 との統合で、ユーザー単位の認可が可能になる。

---

## まとめ

本記事では、有報分析AIパイプラインをFastAPIでラップし、本番デプロイ可能な形にする実装を解説した。

| テーマ | 実装のポイント |
|---|---|
| ルーター設計 | 7責務を `APIRouter` で明確に分離 |
| 認証 | 環境変数 `API_KEY` の有無で開発/本番を自動切替 |
| 非同期化 | `BackgroundTasks` + `run_in_executor` でブロッキング処理を分離 |
| リアルタイム | SSEで進捗を0.5秒間隔でストリーミング |
| PDF保護 | 拡張子・MIME・サイズ・マジックバイトの4重バリデーション |
| Docker化 | `condition: service_healthy` でサービス起動順を制御 |

CLIで動くことと本番で使えることの間には大きな溝がある。FastAPIとDockerの組み合わせは、その溝を埋める現時点でもっとも実践的な選択肢のひとつだ。本実装を足がかりに、Redisキューや認証強化を追加してスケールさせてほしい。

なお、パイプライン全体には 735件のテストが整備されており（3件スキップ）、M1〜M9 の各エージェントの動作が自動検証される。デプロイ後の回帰テストも `pytest` 一発で完了する。

---

本記事は disclosure-multiagent シリーズの一部。
- OSS: https://github.com/Majiro-ns/disclosure-multiagent
- 関連記事: AIで有価証券報告書の開示漏れを自動検出する — Pythonマルチエージェント実装
