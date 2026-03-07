"""
disclosure-multiagent Phase 2 M7-1: EDINET 有報 PDF 自動取得クライアント

使い方:
    USE_MOCK_EDINET=true python3 m7_edinet_client.py --date 2026-01-10
    EDINET_SUBSCRIPTION_KEY=xxx USE_MOCK_EDINET=false python3 m7_edinet_client.py --date 2026-01-10

    # バッチ処理（複数企業一括）
    USE_MOCK_EDINET=true python3 m7_edinet_client.py --batch '{"companies":[{"company_name":"A","year":2023}]}'
"""
from __future__ import annotations
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
import requests

EDINET_DL_BASE  = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf"
EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"

USE_MOCK_EDINET    = os.environ.get("USE_MOCK_EDINET", "true").lower() == "true"
SUBSCRIPTION_KEY   = os.environ.get("EDINET_SUBSCRIPTION_KEY", "")

# DOS対策: 実APIアクセス時の最低待機秒数
REQUEST_DELAY: float = 3.0

_SAMPLES_DIR = Path(__file__).parent.parent / "10_Research" / "samples"

# モック用サンプルデータ（書類種別コード 120 = 有価証券報告書）
MOCK_DOCUMENTS: list[dict] = [
    {"docID": "S100A001", "edinetCode": "E00001", "filerName": "サンプル社A",
     "docTypeCode": "120", "periodEnd": "2023-03-31", "submitDateTime": "2023-06-28"},
    {"docID": "S100B002", "edinetCode": "E00002", "filerName": "サンプル社B",
     "docTypeCode": "120", "periodEnd": "2023-03-31", "submitDateTime": "2023-06-30"},
    {"docID": "S100C003", "edinetCode": "E00003", "filerName": "サンプル社C",
     "docTypeCode": "120", "periodEnd": "2023-06-30", "submitDateTime": "2023-09-29"},
]


@dataclass
class BatchCompanyResult:
    """バッチ分析の1社分の結果"""
    company_name: str
    year: int
    docs: list[dict] = field(default_factory=list)
    downloaded_paths: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        """書類が1件以上取得でき、エラーがない場合 True"""
        return not self.error and len(self.docs) > 0


def validate_edinetcode(code: str) -> bool:
    """EDINETコード形式チェック（E + 5桁数字）"""
    return bool(re.fullmatch(r"E\d{5}", code))


def validate_doc_id(doc_id: str) -> bool:
    """書類管理番号形式チェック（S + 7桁英数字）"""
    return bool(re.fullmatch(r"S[A-Z0-9]{7}", doc_id))


def fetch_document_list(date: str, doc_type_code: str = "120") -> list[dict]:
    """EDINET 書類一覧APIで有報リストを取得。USE_MOCK_EDINET=true でモックデータを返す。"""
    if USE_MOCK_EDINET:
        return [d for d in MOCK_DOCUMENTS if d["docTypeCode"] == doc_type_code]

    if not SUBSCRIPTION_KEY:
        raise RuntimeError(
            "EDINET API には Subscription-Key が必要です。"
            "環境変数 EDINET_SUBSCRIPTION_KEY を設定してください。"
        )

    resp = requests.get(
        f"{EDINET_API_BASE}/documents.json",
        params={"date": date, "type": 2, "Subscription-Key": SUBSCRIPTION_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [r for r in results if r.get("docTypeCode") == doc_type_code]


def download_pdf(doc_id: str, output_dir: str) -> str:
    """EDINET直接DL（認証不要）でPDFを取得。doc_id不正→ValueError、404→FileNotFoundError。"""
    if not validate_doc_id(doc_id):
        raise ValueError(f"無効な書類管理番号: '{doc_id}'（S + 7桁英数字が必要）")

    if USE_MOCK_EDINET:
        # OSS公開用架空企業サンプルPDF（tests/fixtures/sample_yuho.pdf）を優先使用
        sample_yuho = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_yuho.pdf"
        sample_legacy = _SAMPLES_DIR / "company_a.pdf"
        sample = sample_yuho if sample_yuho.exists() else sample_legacy
        if sample.exists():
            return str(sample)
        raise FileNotFoundError(f"モック用サンプルPDFが見つかりません: {sample}")

    time.sleep(REQUEST_DELAY)  # EDINET サーバー負荷軽減（DOS対策: REQUEST_DELAY秒）
    resp = requests.get(f"{EDINET_DL_BASE}/{doc_id}.pdf", timeout=60, stream=True)
    if resp.status_code == 404:
        raise FileNotFoundError(f"書類が見つかりません: docID={doc_id}")
    resp.raise_for_status()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf_path = out / f"{doc_id}.pdf"
    with open(pdf_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return str(pdf_path)


def search_by_company(company_name: str, year: int) -> list[dict]:
    """会社名（部分一致）・年度から有価証券報告書を検索。"""
    if USE_MOCK_EDINET:
        return [d for d in MOCK_DOCUMENTS if company_name in d["filerName"]]

    results: list[dict] = []
    for month in range(1, 13):
        try:
            docs = fetch_document_list(f"{year}-{month:02d}-01")
            results.extend(d for d in docs if company_name in d.get("filerName", ""))
            time.sleep(REQUEST_DELAY)  # DOS対策
        except Exception:
            continue
    return results


def batch_fetch_companies(
    companies: list[dict],
    download_dir: str = "",
    request_delay: float = REQUEST_DELAY,
) -> list[BatchCompanyResult]:
    """複数企業を一括処理してバッチ結果を返す。

    Args:
        companies: 処理対象企業リスト。各要素は {"company_name": str, "year": int}
        download_dir: PDF保存先（空文字列の場合はダウンロードしない）
        request_delay: 企業間の待機秒数（実APIのみ適用。モック時はスキップ）

    Returns:
        各企業の BatchCompanyResult リスト（入力順）
    """
    results: list[BatchCompanyResult] = []
    for i, company in enumerate(companies):
        if i > 0 and not USE_MOCK_EDINET:
            time.sleep(request_delay)

        company_name = company.get("company_name", "")
        year = int(company.get("year", 0))
        start = time.time()
        try:
            docs = search_by_company(company_name, year)
            downloaded: list[str] = []
            if download_dir and docs:
                for j, doc in enumerate(docs):
                    if j > 0 and not USE_MOCK_EDINET:
                        time.sleep(request_delay)
                    try:
                        path = download_pdf(doc["docID"], download_dir)
                        downloaded.append(path)
                    except Exception:
                        pass
            results.append(BatchCompanyResult(
                company_name=company_name,
                year=year,
                docs=docs,
                downloaded_paths=downloaded,
                elapsed_sec=time.time() - start,
            ))
        except Exception as exc:
            results.append(BatchCompanyResult(
                company_name=company_name,
                year=year,
                elapsed_sec=time.time() - start,
                error=str(exc),
            ))
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EDINET 有報 PDF 取得クライアント（M7-1）")
    parser.add_argument("--date", help="書類一覧取得日（YYYY-MM-DD）")
    parser.add_argument("--output", default=str(_SAMPLES_DIR), help="PDF保存先")
    parser.add_argument("--company", help="会社名（部分一致）")
    parser.add_argument("--year", type=int, help="提出年度")
    parser.add_argument(
        "--batch",
        help='バッチ処理JSON: {"companies":[{"company_name":"...","year":2023},...]}',
    )
    args = parser.parse_args()

    mode = "モック" if USE_MOCK_EDINET else "実API"
    print(f"[M7] EDINET クライアント起動（モード: {mode}）")

    if args.batch:
        batch_input = json.loads(args.batch)
        companies = batch_input.get("companies", [])
        print(f"[M7] バッチ処理開始: {len(companies)} 社")
        batch_results = batch_fetch_companies(companies, download_dir=args.output)
        for r in batch_results:
            status = "✅" if r.success else ("⚠️" if not r.error else "❌")
            print(
                f"  {status} {r.company_name}({r.year}): "
                f"{len(r.docs)}件取得 DL={len(r.downloaded_paths)} "
                f"({r.elapsed_sec:.1f}s)"
                + (f" ERROR={r.error}" if r.error else "")
            )
    elif args.date:
        docs = fetch_document_list(args.date)
        print(f"[M7] 書類一覧: {len(docs)} 件 (date={args.date})")
        for d in docs[:5]:
            print(f"  docID={d['docID']}  edinetCode={d['edinetCode']}  filerName={d['filerName']}")
    elif args.company and args.year:
        docs = search_by_company(args.company, args.year)
        print(f"[M7] 検索結果: {len(docs)} 件 (company={args.company}, year={args.year})")
    else:
        parser.print_help()
