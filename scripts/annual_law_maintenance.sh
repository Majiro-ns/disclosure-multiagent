#!/usr/bin/env bash
# annual_law_maintenance.sh — 年次法令更新チェック・メンテナンスガイド (DIS-C09)
#
# 用途:
#   年1回（有報提出期の前後推奨: 3月〜4月）に手動実行し、
#   e-Gov Law API + FSA RSS で開示府令の更新を検知する。
#   差分レポートを生成し、DISCORD_WEBHOOK_URL が設定されていれば通知する。
#
# 使い方:
#   cd /path/to/disclosure-multiagent
#   bash scripts/annual_law_maintenance.sh [--dry-run]
#
# 環境変数 (.env から読み込み):
#   DISCORD_WEBHOOK_URL : Discord Webhook URL（省略時は通知なし）
#   GITHUB_TOKEN        : GitHub API トークン（--yaml-only 使用時は不要）
#   GITHUB_REPO         : "owner/repo" 形式（--yaml-only 使用時は不要）
#
# ⚠️ laws/ への自動書き込みは行わない。
#    出力された queue/backlog/law_update_candidates_*.yaml を確認の上、
#    人間が手動で laws/ を更新すること。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CHECK_PY="$SCRIPT_DIR/check_law_updates.py"

# .env 読み込み（存在する場合）
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
    echo "[INFO] .env を読み込みました"
fi

# 引数処理
DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "[INFO] dry-run モードで実行します（外部への書き込み・通知なし）"
fi

# チェック対象期間: 1年前から今日まで
SINCE_DATE=$(date -d "1 year ago" +%Y-%m-%d 2>/dev/null || date -v-1y +%Y-%m-%d 2>/dev/null || python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(days=365)).isoformat())")
TODAY=$(date +%Y-%m-%d)

echo ""
echo "========================================================"
echo "  disclosure-multiagent 年次法令メンテナンス"
echo "  チェック期間: ${SINCE_DATE} 〜 ${TODAY}"
echo "========================================================"
echo ""

# Python 実行
if [[ -n "$DRY_RUN" ]]; then
    python3 "$CHECK_PY" --since "$SINCE_DATE" --dry-run
else
    python3 "$CHECK_PY" --since "$SINCE_DATE" --yaml-only
fi

EXIT_CODE=$?

echo ""
echo "========================================================"
echo "  laws/ 手動更新ガイド"
echo "========================================================"
echo ""
echo "【STEP 1】更新候補ファイルを確認する"
echo "  cat queue/backlog/law_update_candidates_${SINCE_DATE}.yaml"
echo ""
echo "【STEP 2】e-Gov で法令本文XMLを確認する"
echo "  # 開示府令:"
echo "  curl https://laws.e-gov.go.jp/api/2/lawdata/348M50000040005"
echo "  # 会社法施行規則:"
echo "  curl https://laws.e-gov.go.jp/api/2/lawdata/411M50000010011"
echo ""
echo "【STEP 3】laws/ 配下の対応 YAML を確認し、必要な amendments エントリを特定する"
echo "  ls laws/"
echo "  cat laws/disclosure_ordinance.yaml | grep -A5 'amendments'"
echo ""
echo "【STEP 4】変更内容を独自表現で laws/*.yaml に反映する"
echo "  ⚠️  著作権注意: 法令本文の直接コピーは禁止。独自の言葉で要約すること。"
echo "  ⚠️  laws/ への自動書き込みは禁止。必ず人間がレビューした上で手動更新すること。"
echo ""
echo "【STEP 5】全テストで動作確認する"
echo "  cd $PROJECT_DIR"
echo "  python3 -m pytest scripts/ -x -q"
echo ""
echo "【STEP 6】commit + push する"
echo "  git add laws/"
echo "  git commit -m 'chore(laws): 年次法令更新 ${TODAY}'"
echo "  git push"
echo ""
echo "========================================================"
echo "  実行完了 (exit code: ${EXIT_CODE})"
echo "========================================================"
echo ""

exit $EXIT_CODE
