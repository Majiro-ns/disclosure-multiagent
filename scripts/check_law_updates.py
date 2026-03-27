"""法令更新チェックスクリプト (DIS-C09)

e-Gov Law API v2 + FSA RSS で開示府令の更新を検知し、
変更があれば GitHub Issue を自動作成する。
また、更新候補タスクを queue/backlog/ に YAML 形式で出力し、
Discord Webhook に通知する（任意）。

使い方:
    # 直近30日の更新チェック（dry-run）
    python3 check_law_updates.py --dry-run

    # 指定日以降の更新チェック + Issue作成 + YAML出力
    python3 check_law_updates.py --since 2026-01-01

    # YAML候補ファイルのみ出力（Issue作成なし）
    python3 check_law_updates.py --since 2025-04-01 --yaml-only

    # 手動実行（dry-run）
    python3 check_law_updates.py --since 2025-04-01 --dry-run

環境変数:
    GITHUB_TOKEN       : GitHub API トークン（Issue作成に必要）
    GITHUB_REPO        : "owner/repo" 形式（Issue作成先）
    DISCORD_WEBHOOK_URL: Discord Webhook URL（通知に使用、省略可）
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate
from typing import Optional

try:
    import yaml as _yaml_module
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

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


# ─── FSA RSS ─────────────────────────────────────────────────────────────────

FSA_RSS_URL = "https://www.fsa.go.jp/fsaNewsListAll_rss2.xml"
FSA_TIMEOUT = 30  # seconds

# 開示・法令改正関連キーワード（タイトルに含まれる場合に関連記事と判断）
FSA_DISCLOSURE_KEYWORDS: list[str] = [
    "開示", "府令", "有価証券", "財務諸表", "連結", "IFRS",
    "企業会計", "サステナビリティ", "内閣府令", "法律",
]


def fetch_fsa_rss() -> str:
    """FSA新着情報RSSフィード（RSS 2.0）を取得する。

    Returns:
        RSSフィードXMLテキスト。

    Raises:
        urllib.error.URLError: ネットワークエラー。
    """
    logger.info("FSA RSS リクエスト: %s", FSA_RSS_URL)
    req = urllib.request.Request(
        FSA_RSS_URL,
        headers={"User-Agent": "disclosure-multiagent/check_law_updates"},
    )
    with urllib.request.urlopen(req, timeout=FSA_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def parse_fsa_rss(rss_text: str) -> list[dict]:
    """FSA RSS 2.0 XMLをパースしてアイテムリストを返す。

    Args:
        rss_text: FSA RSSフィードのXMLテキスト。

    Returns:
        [{"title": str, "link": str, "pub_date": str}, ...] のリスト。
        パースエラーの場合は空リスト。
    """
    try:
        root = ET.fromstring(rss_text)
    except ET.ParseError as e:
        logger.error("FSA RSS XMLパースエラー: %s", e)
        return []

    items: list[dict] = []
    for item_el in root.findall(".//item"):
        title = _text(item_el, "title")
        link = _text(item_el, "link")
        pub_date = _text(item_el, "pubDate")
        if title or link:
            items.append({"title": title, "link": link, "pub_date": pub_date})

    logger.info("FSA RSS 取得件数: %d 件", len(items))
    return items


def _parse_rss_date(pub_date_str: str) -> Optional[date]:
    """RSS pubDate（RFC 2822形式）を date 型に変換する。

    例: "Tue, 24 Mar 2026 17:00:00 JST" → date(2026, 3, 24)

    Args:
        pub_date_str: pubDate文字列。

    Returns:
        date オブジェクト。パース失敗時は None。
    """
    t = parsedate(pub_date_str)
    if t is None:
        return None
    try:
        return date(t[0], t[1], t[2])
    except (ValueError, IndexError):
        return None


def filter_disclosure_rss(items: list[dict], since_date: date) -> list[dict]:
    """FSA RSSアイテムから開示関連記事を抽出する。

    条件:
      - pub_date が since_date 以降
      - タイトルに FSA_DISCLOSURE_KEYWORDS のいずれかを含む

    Args:
        items: parse_fsa_rss() の返り値。
        since_date: 対象開始日（この日以降の記事を対象）。

    Returns:
        条件に一致したアイテムのリスト。
    """
    matched: list[dict] = []
    for item in items:
        item_date = _parse_rss_date(item.get("pub_date", ""))
        if item_date is None or item_date < since_date:
            continue
        title = item.get("title", "")
        if any(kw in title for kw in FSA_DISCLOSURE_KEYWORDS):
            matched.append(item)
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


def build_issue_body(
    updates: list[dict],
    since_date: date,
    fsa_items: Optional[list[dict]] = None,
) -> str:
    """更新法令リスト + FSA RSS記事から GitHub Issue 本文を生成する。

    Args:
        updates: filter_watched_laws() の返り値。
        since_date: 更新チェック開始日。
        fsa_items: filter_disclosure_rss() の返り値（省略可）。

    Returns:
        Markdown 形式の Issue 本文。
    """
    lines = [
        f"## 法令更新検知レポート",
        f"",
        f"**チェック期間**: {since_date} 以降",
        f"**e-Gov 検知件数**: {len(updates)} 件",
        f"**FSA RSS 検知件数**: {len(fsa_items) if fsa_items else 0} 件",
        f"",
        f"### 更新された監視対象法令（e-Gov）",
        f"",
    ]
    if updates:
        for u in updates:
            lines.append(f"- **{u['watched_name']}**")
            lines.append(f"  - 法令ID: `{u['law_id']}`")
            if u.get("law_title"):
                lines.append(f"  - 法令名: {u['law_title']}")
            if u.get("promulgation_date"):
                lines.append(f"  - 公布日: {u['promulgation_date']}")
            lines.append(f"  - e-Gov: https://laws.e-gov.go.jp/law/{u['law_id']}")
            lines.append(f"")
    else:
        lines.append(f"（監視対象法令の更新なし）")
        lines.append(f"")

    if fsa_items:
        lines += [
            f"### FSA新着（開示関連）",
            f"",
        ]
        for item in fsa_items:
            lines.append(f"- [{item['title']}]({item['link']})")
            if item.get("pub_date"):
                lines.append(f"  - 公開日: {item['pub_date']}")
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


# ─── YAML候補ファイル出力 ─────────────────────────────────────────────────────

def write_update_candidates_yaml(
    updates: list[dict],
    since_date: date,
    fsa_items: Optional[list[dict]] = None,
    output_dir: Optional[pathlib.Path] = None,
) -> Optional[pathlib.Path]:
    """更新候補タスクを YAML ファイルとして queue/backlog/ に出力する。

    ⚠️ このファイルは「更新候補の通知」であり、laws/ への自動書き込みは行わない。
    人間がレビューした上で手動で laws/ を更新すること。

    Args:
        updates: filter_watched_laws() の返り値（e-Gov 検知分）。
        since_date: 更新チェック開始日。
        fsa_items: filter_disclosure_rss() の返り値（FSA RSS 検知分）。
        output_dir: 出力ディレクトリ（省略時はスクリプト起点の ../queue/backlog/）。

    Returns:
        書き込んだファイルの Path。更新がない場合 / 書き込み失敗時は None。
    """
    if not updates and not fsa_items:
        return None

    # デフォルト出力先: scripts/../queue/backlog/
    if output_dir is None:
        output_dir = pathlib.Path(__file__).parent.parent / "queue" / "backlog"

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"law_update_candidates_{since_date.isoformat()}.yaml"
    output_path = output_dir / filename

    # YAML データ構造
    candidates: list[dict] = []
    for u in updates:
        candidates.append({
            "source": "egov",
            "law_id": u["law_id"],
            "law_name": u.get("watched_name", u.get("law_title", "")),
            "promulgation_date": u.get("promulgation_date", ""),
            "egov_url": f"https://laws.e-gov.go.jp/law/{u['law_id']}",
            "action_required": "laws/ 配下の対応YAMLを確認し、必要に応じて手動更新せよ",
            "auto_write_prohibited": True,
        })

    for item in (fsa_items or []):
        candidates.append({
            "source": "fsa_rss",
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "pub_date": item.get("pub_date", ""),
            "action_required": "FSA通知内容を確認し、laws/ または profiles/ の更新要否を判断せよ",
            "auto_write_prohibited": True,
        })

    data = {
        "generated_at": date.today().isoformat(),
        "since_date": since_date.isoformat(),
        "egov_count": len(updates),
        "fsa_count": len(fsa_items) if fsa_items else 0,
        "warning": "laws/ への自動書き込みは禁止。必ず人間レビュー後に手動更新すること。",
        "candidates": candidates,
    }

    try:
        if _YAML_AVAILABLE:
            with open(output_path, "w", encoding="utf-8") as f:
                _yaml_module.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        else:
            # PyYAML 非インストール時は JSON 形式で書き込む
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("YAML候補ファイル出力: %s", output_path)
        return output_path
    except OSError as e:
        logger.error("YAML出力失敗: %s", e)
        return None


# ─── Discord Webhook 通知 ─────────────────────────────────────────────────────

DISCORD_TIMEOUT = 15  # seconds


def notify_discord(
    webhook_url: str,
    updates: list[dict],
    since_date: date,
    fsa_items: Optional[list[dict]] = None,
    yaml_path: Optional[pathlib.Path] = None,
) -> bool:
    """Discord Webhook に法令更新検知を通知する。

    Args:
        webhook_url: Discord Webhook URL。
        updates: filter_watched_laws() の返り値。
        since_date: 更新チェック開始日。
        fsa_items: filter_disclosure_rss() の返り値（省略可）。
        yaml_path: write_update_candidates_yaml() が返したファイルパス（省略可）。

    Returns:
        送信成功時 True、失敗時 False。
    """
    total = len(updates) + len(fsa_items or [])
    title = f"📋 法令更新検知: {total} 件 (e-Gov:{len(updates)} / FSA:{len(fsa_items or [])})"

    lines = [f"**{title}**", f"チェック期間: {since_date} 以降", ""]
    for u in updates:
        lines.append(f"• **{u.get('watched_name', u['law_id'])}** — {u.get('promulgation_date', '')}")
    for item in (fsa_items or []):
        lines.append(f"• [FSA] {item.get('title', '')}")
    if yaml_path:
        lines.append(f"\n📄 候補ファイル: `{yaml_path.name}`")
    lines.append("\n> ⚠️ laws/ の自動更新は禁止。人間レビュー後に手動更新すること。")

    payload = json.dumps({"content": "\n".join(lines)}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=DISCORD_TIMEOUT) as resp:
            logger.info("Discord通知送信: HTTP %d", resp.status)
            return True
    except Exception as e:
        logger.warning("Discord通知失敗（継続）: %s", e)
        return False


def run(since_date: date, dry_run: bool = False, yaml_only: bool = False) -> int:
    """法令更新チェックを実行する（e-Gov API + FSA RSS 両方）。

    Args:
        since_date: 更新チェック開始日。
        dry_run: True の場合 Issue を作成せずに結果を表示のみ（YAML出力・Discord通知も行わない）。
        yaml_only: True の場合 YAML候補ファイル出力 + Discord通知のみ行い、Issue作成はスキップ。

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

    # ④ FSA RSS チェック（ベストエフォート: 失敗しても継続）
    fsa_matched: list[dict] = []
    try:
        rss_text = fetch_fsa_rss()
        rss_items = parse_fsa_rss(rss_text)
        fsa_matched = filter_disclosure_rss(rss_items, since_date)
    except Exception as e:
        logger.warning("FSA RSS 取得スキップ: %s", e)

    # 両方とも更新なしなら終了
    if not matched and not fsa_matched:
        logger.info("監視対象の更新なし（%s 以降）", since_date)
        return 0

    # ⑤ 結果表示
    if matched:
        print(f"\n✅ {len(matched)} 件の監視対象法令更新を検知（e-Gov）:")
        for u in matched:
            print(f"  - {u['watched_name']} ({u['law_id']})")
            if u.get("promulgation_date"):
                print(f"    公布日: {u['promulgation_date']}")

    if fsa_matched:
        print(f"\n📰 {len(fsa_matched)} 件の開示関連FSA新着を検知:")
        for item in fsa_matched:
            print(f"  - {item['title']}")

    if dry_run:
        print("\n[dry-run] Issue作成・YAML出力・Discord通知をスキップ")
        print("\n--- Issue 本文プレビュー ---")
        print(build_issue_body(matched, since_date, fsa_items=fsa_matched))
        return 0

    # ⑥ YAML候補ファイル出力（laws/ への自動書き込みは禁止）
    yaml_path = write_update_candidates_yaml(matched, since_date, fsa_items=fsa_matched)
    if yaml_path:
        print(f"\n📄 更新候補ファイル出力: {yaml_path}")
        print("   ⚠️  laws/ の自動更新は禁止。このファイルを確認の上、人間が手動更新すること。")

    # ⑦ Discord Webhook 通知（任意: DISCORD_WEBHOOK_URL 未設定時はスキップ）
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if webhook_url:
        notify_discord(webhook_url, matched, since_date, fsa_items=fsa_matched, yaml_path=yaml_path)
    else:
        logger.info("DISCORD_WEBHOOK_URL 未設定のため Discord 通知をスキップ")

    if yaml_only:
        print("\n[yaml-only] GitHub Issue 作成をスキップ")
        return 0

    # ⑧ GitHub Issue 作成
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        logger.error(
            "GITHUB_TOKEN と GITHUB_REPO の環境変数が必要です。"
            "dry-run モードには --dry-run を、YAML出力のみには --yaml-only を指定してください。"
        )
        return 1

    total = len(matched) + len(fsa_matched)
    title = f"[法令更新] {total} 件の更新を検知（e-Gov:{len(matched)} / FSA:{len(fsa_matched)}）({since_date})"
    body = build_issue_body(matched, since_date, fsa_items=fsa_matched)
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
        help="Issue を作成せずに結果表示のみ（YAML出力・Discord通知も行わない）",
    )
    parser.add_argument(
        "--yaml-only",
        action="store_true",
        help="YAML候補ファイル出力 + Discord通知のみ行い、GitHub Issue作成はスキップ",
    )
    args = parser.parse_args()

    if args.since:
        try:
            since_date = date.fromisoformat(args.since)
        except ValueError:
            parser.error(f"日付形式が不正です: {args.since} (YYYY-MM-DD)")
    else:
        since_date = date.today() - timedelta(days=30)

    exit(run(since_date, dry_run=args.dry_run, yaml_only=args.yaml_only))


if __name__ == "__main__":
    main()
