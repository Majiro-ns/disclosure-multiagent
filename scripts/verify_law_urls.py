#!/usr/bin/env python3
"""
verify_law_urls.py — laws/ 配下のYAMLからURLを抽出してHTTP HEAD検証するスクリプト
cmd_360k_a4c (P3) により作成

使い方:
    python scripts/verify_law_urls.py
    python scripts/verify_law_urls.py --timeout 15
    python scripts/verify_law_urls.py --output results.json
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests
import yaml

LAWS_DIR = Path(__file__).parent.parent / "laws"
TIMEOUT_DEFAULT = 10
USER_AGENT = "disclosure-multiagent/1.0 (URL verification; +https://github.com/)"


@dataclass
class UrlResult:
    yaml_file: str
    amendment_id: str
    url: str
    source_confirmed: Optional[bool]
    status: str          # "valid" | "invalid" | "timeout" | "error"
    http_code: Optional[int]
    reason: str


def load_yaml_urls(laws_dir: Path) -> list[UrlResult]:
    """laws/ 配下の全YAMLから (amendment_id, url, source_confirmed) を抽出する"""
    results = []
    yaml_files = sorted(laws_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"[WARN] laws/ にYAMLファイルが見つかりません: {laws_dir}", file=sys.stderr)
        return results

    for yaml_path in yaml_files:
        try:
            with yaml_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"[WARN] {yaml_path.name} 読み込みエラー: {e}", file=sys.stderr)
            continue

        amendments = data.get("amendments", []) if isinstance(data, dict) else []
        for amendment in amendments:
            if not isinstance(amendment, dict):
                continue
            url = amendment.get("source", "")
            if not url or not str(url).startswith("http"):
                continue
            results.append(UrlResult(
                yaml_file=yaml_path.name,
                amendment_id=amendment.get("id", "unknown"),
                url=str(url),
                source_confirmed=amendment.get("source_confirmed"),
                status="pending",
                http_code=None,
                reason="",
            ))

    return results


def verify_url(url: str, timeout: int = TIMEOUT_DEFAULT) -> tuple[str, Optional[int], str]:
    """
    URLにHEAD requestを送信して検証する。
    HEADが405の場合はGETにフォールバック。

    Returns:
        (status, http_code, reason)
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 405:
            # HEAD not allowed → GETで再試行（レスポンスボディはストリームのみ）
            resp = requests.get(url, headers=headers, timeout=timeout,
                                allow_redirects=True, stream=True)
            resp.close()
        code = resp.status_code
        if 200 <= code < 400:
            return "valid", code, f"HTTP {code}"
        else:
            return "invalid", code, f"HTTP {code}"
    except requests.exceptions.Timeout:
        return "timeout", None, f"タイムアウト ({timeout}秒)"
    except requests.exceptions.ConnectionError as e:
        return "error", None, f"接続エラー: {type(e).__name__}"
    except requests.exceptions.RequestException as e:
        return "error", None, f"リクエストエラー: {type(e).__name__}"


def print_report(results: list[UrlResult]) -> None:
    """検証結果をコンソールに表示する"""
    valid = [r for r in results if r.status == "valid"]
    invalid = [r for r in results if r.status == "invalid"]
    timeout = [r for r in results if r.status == "timeout"]
    error = [r for r in results if r.status == "error"]

    print("\n" + "=" * 70)
    print("URL検証レポート — disclosure-multiagent laws/")
    print("=" * 70)
    print(f"対象URL総数 : {len(results)}")
    print(f"  ✅ 有効    : {len(valid)}")
    print(f"  ❌ 無効    : {len(invalid)}")
    print(f"  ⏱ タイムアウト: {len(timeout)}")
    print(f"  ⚠️  エラー  : {len(error)}")
    print()

    if invalid or timeout or error:
        print("── 問題あり ──────────────────────────────────────────────")
        for r in invalid + timeout + error:
            icon = "❌" if r.status == "invalid" else ("⏱" if r.status == "timeout" else "⚠️ ")
            confirmed_tag = f" [source_confirmed={r.source_confirmed}]" if r.source_confirmed is not None else ""
            print(f"{icon} {r.yaml_file} / {r.amendment_id}{confirmed_tag}")
            print(f"   URL   : {r.url}")
            print(f"   状態  : {r.reason}")
            print()

    if valid:
        print("── 有効 ──────────────────────────────────────────────────")
        for r in valid:
            confirmed_tag = "✅confirmed" if r.source_confirmed else ("⚠️未確認" if r.source_confirmed is False else "")
            print(f"  {r.amendment_id} ({r.yaml_file}) {confirmed_tag} — {r.reason}")

    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description="laws/ YAMLのURL有効性検証")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT,
                        help=f"タイムアウト秒数 (デフォルト: {TIMEOUT_DEFAULT}秒)")
    parser.add_argument("--output", type=str, default=None,
                        help="JSON結果を保存するファイルパス (省略可)")
    parser.add_argument("--dry-run", action="store_true",
                        help="URL抽出のみ（HTTP送信なし）")
    args = parser.parse_args()

    print(f"[INFO] laws/ ディレクトリ: {LAWS_DIR}")
    url_entries = load_yaml_urls(LAWS_DIR)
    print(f"[INFO] 抽出URL数: {len(url_entries)}")

    if args.dry_run:
        for r in url_entries:
            print(f"  {r.yaml_file} / {r.amendment_id}: {r.url}")
        return 0

    if not url_entries:
        print("[WARN] 検証するURLがありませんでした。")
        return 0

    print(f"[INFO] HTTP検証開始 (timeout={args.timeout}秒) ...\n")
    for i, entry in enumerate(url_entries, 1):
        print(f"  [{i:02d}/{len(url_entries):02d}] {entry.amendment_id} ... ", end="", flush=True)
        status, code, reason = verify_url(entry.url, args.timeout)
        entry.status = status
        entry.http_code = code
        entry.reason = reason
        icon = "✅" if status == "valid" else ("❌" if status == "invalid" else "⏱")
        print(f"{icon} {reason}")
        # サーバー負荷対策のため少し待機
        if i < len(url_entries):
            time.sleep(0.5)

    print_report(url_entries)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in url_entries], f, ensure_ascii=False, indent=2)
        print(f"\n[INFO] 結果をJSONに保存: {out_path}")

    # 問題ありの場合は終了コード1
    has_issues = any(r.status != "valid" for r in url_entries)
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
