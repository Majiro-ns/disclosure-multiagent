"""法令更新チェックスクリプト (DIS-C09)

e-Gov Law API v2 で開示府令の更新を検知し、
変更があれば GitHub Issue を自動作成する。

使い方:
    # 直近30日の更新チェック（dry-run）
    python3 check_law_updates.py --dry-run

    # 指定日以降の更新チェック + Issue作成
    python3 check_law_updates.py --since 2026-01-01

    # 手動実行（dry-run）
    python3 check_law_updates.py --since 2025-04-01 --dry-run

環境変数:
    GITHUB_TOKEN : GitHub API トークン（Issue作成に必要）
    GITHUB_REPO  : "owner/repo" 形式（Issue作成先）
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── 監視対象法令 ─────────────────────────────────────────────────────────────

WATCHED_LAWS: dict[str, str] = {
    "348M50000040005": "企業内容等の開示に関する内閣府令（開示府令）",
    "411M50000010011": "会社法施行規則",
    "427M60000008019": "特定事業者の事業報告等に係る事項の開示に関する内閣府令（CSR開示府令）",
}

# ─── e-Gov Law API v2 ─────────────────────────────────────────────────────────

EGOV_API_BASE = "https://laws.e-gov.go.jp/api/2"
EGOV_TIMEOUT = 30  # seconds


def fetch_egov_updates(since_date: date) -> str:
    """e-Gov Law API v2 から指定日以降の更新法令XMLを取得する。

    Args:
        since_date: 更新チェック開始日（この日以降の更新を取得）。

    Returns:
        レスポンスXMLテキスト。

    Raises:
        urllib.error.URLError: ネットワークエラー。
        RuntimeError: APIエラーレスポンス。
    """
    date_str = since_date.strftime("%Y%m%d")
    url = f"{EGOV_API_BASE}/updatelawlists/{date_str}"
    logger.info("e-Gov API リクエスト: %s", url)
    req = urllib.request.Request(url, headers={"Accept": "application/xml"})
    with urllib.request.urlopen(req, timeout=EGOV_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def parse_law_updates(xml_text: str) -> list[dict]:
    """e-Gov API のXMLレスポンスをパースして更新法令リストを返す。

    Args:
        xml_text: e-Gov API からのXMLレスポンス。

    Returns:
        [{"law_id": str, "law_title": str, "promulgation_date": str}, ...] のリスト。
        APIエラー（Code != 0）の場合は空リスト。
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("XMLパースエラー: %s", e)
        return []

    # Result/Code チェック
    code_el = root.find(".//Result/Code")
    if code_el is not None and code_el.text != "0":
        msg_el = root.find(".//Result/Message")
        logger.warning("APIエラー Code=%s Message=%s", code_el.text, msg_el.text if msg_el is not None else "")
        return []

    updates: list[dict] = []
    # エレメント名はe-Gov API v2の実仕様に準拠
    for law_el in root.findall(".//LawRevision"):
        law_id = _text(law_el, "LawId")
        law_title = _text(law_el, "LawTitle")
        promulgation_date = _text(law_el, "PromulgationDate")
        if law_id:
            updates.append({
                "law_id": law_id,
                "law_title": law_title,
                "promulgation_date": promulgation_date,
            })

    logger.info("取得件数: %d 件", len(updates))
    return updates


def _text(el: ET.Element, tag: str) -> str:
    """子要素のテキストを返す（存在しない場合は空文字）。"""
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def filter_watched_laws(updates: list[dict]) -> list[dict]:
    """監視対象法令（WATCHED_LAWS）の更新のみフィルタして返す。

    Args:
        updates: parse_law_updates() の返り値。

    Returns:
        WATCHED_LAWS に含まれる法令の更新リスト。
        各要素に "watched_name" キーを追加。
    """
    matched: list[dict] = []
    for u in updates:
        if u["law_id"] in WATCHED_LAWS:
            u["watched_name"] = WATCHED_LAWS[u["law_id"]]
            matched.append(u)
    return matched


# ─── GitHub Issue 作成 ────────────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com"
ISSUE_LABEL = "law-update"


def create_github_issue(
    token: str,
    repo: str,
    title: str,
    body: str,
) -> Optional[str]:
    """GitHub REST API で Issue を作成する。

    Args:
        token: GITHUB_TOKEN。
        repo: "owner/repo" 形式のリポジトリ名。
        title: Issue タイトル。
        body: Issue 本文（Markdown）。

    Returns:
        作成した Issue の URL（失敗時は None）。
    """
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues"
    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": [ISSUE_LABEL],
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            issue_url = result.get("html_url", "")
            logger.info("Issue作成: %s", issue_url)
            return issue_url
    except urllib.error.HTTPError as e:
        logger.error("Issue作成失敗: HTTP %d %s", e.code, e.reason)
        return None


def build_issue_body(updates: list[dict], since_date: date) -> str:
    """更新法令リストから GitHub Issue 本文を生成する。

    Args:
        updates: filter_watched_laws() の返り値。
        since_date: 更新チェック開始日。

    Returns:
        Markdown 形式の Issue 本文。
    """
    lines = [
        f"## 法令更新検知レポート",
        f"",
        f"**チェック期間**: {since_date} 以降",
        f"**検知件数**: {len(updates)} 件",
        f"",
        f"### 更新された監視対象法令",
        f"",
    ]
    for u in updates:
        lines.append(f"- **{u['watched_name']}**")
        lines.append(f"  - 法令ID: `{u['law_id']}`")
        if u.get("law_title"):
            lines.append(f"  - 法令名: {u['law_title']}")
        if u.get("promulgation_date"):
            lines.append(f"  - 公布日: {u['promulgation_date']}")
        lines.append(f"  - e-Gov: https://laws.e-gov.go.jp/law/{u['law_id']}")
        lines.append(f"")

    lines += [
        f"### 対応手順",
        f"",
        f"1. e-Gov Law API で法令本文XMLを確認",
        f"   ```",
        f"   curl https://laws.e-gov.go.jp/api/2/lawdata/{{law_id}}",
        f"   ```",
        f"2. `laws/` 配下の対応YAMLを確認し、更新が必要な `amendments` エントリを特定",
        f"3. 変更内容を独自表現で `laws/*.yaml` に反映（著作権注意）",
        f"4. `python3 -m pytest scripts/ -x` で全テストPASS確認",
        f"5. commit + push",
        f"",
        f"> ⚠️ laws/ への自動書き込みは禁止。必ず人間レビュー後に手動更新すること。",
        f"",
        f"---",
        f"*このIssueは `scripts/check_law_updates.py` により自動生成されました。*",
    ]
    return "\n".join(lines)


# ─── メイン ───────────────────────────────────────────────────────────────────


def run(since_date: date, dry_run: bool = False) -> int:
    """法令更新チェックを実行する。

    Args:
        since_date: 更新チェック開始日。
        dry_run: True の場合 Issue を作成せずに結果を表示のみ。

    Returns:
        終了コード（0: 正常, 1: エラー）。
    """
    # ① e-Gov API から更新法令取得
    try:
        xml_text = fetch_egov_updates(since_date)
    except Exception as e:
        logger.error("e-Gov API 取得失敗: %s", e)
        return 1

    # ② XMLパース
    all_updates = parse_law_updates(xml_text)

    # ③ 監視対象のみフィルタ
    matched = filter_watched_laws(all_updates)

    if not matched:
        logger.info("監視対象法令の更新なし（%s 以降）", since_date)
        return 0

    # ④ 結果表示
    print(f"\n✅ {len(matched)} 件の監視対象法令更新を検知:")
    for u in matched:
        print(f"  - {u['watched_name']} ({u['law_id']})")
        if u.get("promulgation_date"):
            print(f"    公布日: {u['promulgation_date']}")

    if dry_run:
        print("\n[dry-run] Issue作成をスキップ")
        print("\n--- Issue 本文プレビュー ---")
        print(build_issue_body(matched, since_date))
        return 0

    # ⑤ GitHub Issue 作成
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        logger.error(
            "GITHUB_TOKEN と GITHUB_REPO の環境変数が必要です。"
            "dry-run モードには --dry-run を指定してください。"
        )
        return 1

    title = f"[法令更新] {len(matched)} 件の監視対象法令更新を検知 ({since_date})"
    body = build_issue_body(matched, since_date)
    issue_url = create_github_issue(token, repo, title, body)
    if issue_url:
        print(f"\nGitHub Issue 作成: {issue_url}")
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="e-Gov Law API v2 で法令更新を検知する (DIS-C09)")
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="更新チェック開始日（デフォルト: 30日前）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Issue を作成せずに結果表示のみ",
    )
    args = parser.parse_args()

    if args.since:
        try:
            since_date = date.fromisoformat(args.since)
        except ValueError:
            parser.error(f"日付形式が不正です: {args.since} (YYYY-MM-DD)")
    else:
        since_date = date.today() - timedelta(days=30)

    exit(run(since_date, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
