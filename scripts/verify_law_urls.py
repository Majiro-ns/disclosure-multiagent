#!/usr/bin/env python3
"""
verify_law_urls.py — laws/ 配下のYAMLからURLを抽出してHTTP HEAD検証するスクリプト
cmd_360k_a4c (P3) により作成
dis_b05 (DIS-B05) にて強化: SSL fallback / ブラウザUA / YAML自動更新

使い方:
    python scripts/verify_law_urls.py
    python scripts/verify_law_urls.py --timeout 15
    python scripts/verify_law_urls.py --output results.json
    python scripts/verify_law_urls.py --update-yaml
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests
import yaml

LAWS_DIR = Path(__file__).parent.parent / "laws"
TIMEOUT_DEFAULT = 10
# ブラウザに見せかけることでUser-Agent制限サーバーに対応
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


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
    SSLErrorの場合はverify=Falseで再試行（サーバー側中間証明書欠落への対応）。

    Returns:
        (status, http_code, reason)
        status: "valid" | "valid_ssl_warn" | "invalid" | "timeout" | "error"
    """
    headers = {"User-Agent": USER_AGENT}

    def _do_request(verify_ssl: bool) -> tuple[str, Optional[int], str]:
        try:
            resp = requests.head(url, headers=headers, timeout=timeout,
                                 allow_redirects=True, verify=verify_ssl)
            if resp.status_code == 405:
                resp = requests.get(url, headers=headers, timeout=timeout,
                                    allow_redirects=True, stream=True, verify=verify_ssl)
                resp.close()
            code = resp.status_code
            if 200 <= code < 400:
                return "valid", code, f"HTTP {code}"
            else:
                return "invalid", code, f"HTTP {code}"
        except requests.exceptions.Timeout:
            return "timeout", None, f"タイムアウト ({timeout}秒)"
        except requests.exceptions.SSLError:
            return "ssl_error", None, "SSLError"
        except requests.exceptions.ConnectionError as e:
            return "error", None, f"接続エラー: {type(e).__name__}"
        except requests.exceptions.RequestException as e:
            return "error", None, f"リクエストエラー: {type(e).__name__}"

    status, code, reason = _do_request(verify_ssl=True)
    if status == "ssl_error":
        # SSLError → verify=False で再試行（中間証明書欠落サーバー対応）
        status2, code2, reason2 = _do_request(verify_ssl=False)
        if status2 == "valid":
            return "valid_ssl_warn", code2, f"HTTP {code2} (SSL証明書検証スキップ: サーバー側中間証明書欠落)"
        return "error", code2, f"SSLError + {reason2}"
    return status, code, reason


def update_yaml_source_confirmed(laws_dir: Path, results: list["UrlResult"]) -> dict[str, int]:
    """
    検証結果に基づいてYAMLファイルの source_confirmed を更新する。
    valid / valid_ssl_warn → source_confirmed: true
    それ以外 → 変更なし

    Returns: {"updated": N, "skipped": M}
    """
    confirmable = {r.url for r in results if r.status in ("valid", "valid_ssl_warn")}
    stats = {"updated": 0, "skipped": 0}

    for yaml_path in sorted(laws_dir.glob("*.yaml")):
        text = yaml_path.read_text(encoding="utf-8")
        original = text

        # source_confirmed: false の行を探し、直前の source: "URL" と対応させて更新
        # パターン: source: "URL"\n    source_confirmed: false
        def replace_if_confirmable(m: re.Match) -> str:
            url = m.group(1)
            rest = m.group(2)
            if url in confirmable:
                # false → true に置換（インラインコメントは削除）
                return f'source: "{url}"\n{rest}source_confirmed: true'
            return m.group(0)

        # source: "URL" の次の source_confirmed: false 行を対応させる
        pattern = re.compile(
            r'source: "([^"]+)"\n([ \t]*)source_confirmed: false[^\n]*',
        )
        new_text = pattern.sub(replace_if_confirmable, text)

        if new_text != original:
            yaml_path.write_text(new_text, encoding="utf-8")
            updated_count = len(pattern.findall(original)) - len(
                re.findall(r'source_confirmed: false', new_text)
            )
            stats["updated"] += max(1, updated_count)
            print(f"  [UPDATED] {yaml_path.name}")
        else:
            stats["skipped"] += 1

    return stats


def print_report(results: list["UrlResult"]) -> None:
    """検証結果をコンソールに表示する"""
    valid = [r for r in results if r.status == "valid"]
    ssl_warn = [r for r in results if r.status == "valid_ssl_warn"]
    invalid = [r for r in results if r.status == "invalid"]
    timeout = [r for r in results if r.status == "timeout"]
    error = [r for r in results if r.status == "error"]

    print("\n" + "=" * 70)
    print("URL検証レポート — disclosure-multiagent laws/")
    print("=" * 70)
    print(f"対象URL総数 : {len(results)}")
    print(f"  ✅ 有効          : {len(valid)}")
    print(f"  ⚠️  有効(SSL警告): {len(ssl_warn)}")
    print(f"  ❌ 無効          : {len(invalid)}")
    print(f"  ⏱ タイムアウト  : {len(timeout)}")
    print(f"  ✗  エラー       : {len(error)}")
    print()

    if ssl_warn:
        print("── SSL警告（有効・source_confirmed: true に更新対象） ────────")
        for r in ssl_warn:
            print(f"  ⚠️  {r.amendment_id} ({r.yaml_file})")
            print(f"     URL  : {r.url}")
            print(f"     状態 : {r.reason}")
        print()

    if invalid or timeout or error:
        print("── 問題あり（要対応） ────────────────────────────────────────")
        for r in invalid + timeout + error:
            icon = "❌" if r.status == "invalid" else ("⏱" if r.status == "timeout" else "✗ ")
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
    parser.add_argument("--update-yaml", action="store_true",
                        help="有効URLのsource_confirmed: false → true に自動更新")
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
    seen_urls: dict[str, tuple[str, Optional[int], str]] = {}
    for i, entry in enumerate(url_entries, 1):
        print(f"  [{i:02d}/{len(url_entries):02d}] {entry.amendment_id} ... ", end="", flush=True)
        if entry.url in seen_urls:
            # 同じURLは再検証せずキャッシュ利用
            status, code, reason = seen_urls[entry.url]
            print(f"(キャッシュ) ", end="")
        else:
            status, code, reason = verify_url(entry.url, args.timeout)
            seen_urls[entry.url] = (status, code, reason)
            if i < len(url_entries):
                time.sleep(0.3)
        entry.status = status
        entry.http_code = code
        entry.reason = reason
        icon = "✅" if status in ("valid", "valid_ssl_warn") else ("❌" if status == "invalid" else "⏱")
        print(f"{icon} {reason}")

    print_report(url_entries)

    if args.update_yaml:
        print("\n[INFO] YAML自動更新開始 (source_confirmed: false → true) ...")
        stats = update_yaml_source_confirmed(LAWS_DIR, url_entries)
        print(f"[INFO] YAML更新完了: {stats['updated']}ファイル更新, {stats['skipped']}ファイルスキップ")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in url_entries], f, ensure_ascii=False, indent=2)
        print(f"\n[INFO] 結果をJSONに保存: {out_path}")

    # 真に無効な場合のみ終了コード1（SSL警告・タイムアウトは除外）
    has_hard_issues = any(r.status in ("invalid", "error", "timeout") for r in url_entries)
    return 1 if has_hard_issues else 0


if __name__ == "__main__":
    sys.exit(main())
