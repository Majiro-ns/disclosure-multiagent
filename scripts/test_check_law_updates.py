"""check_law_updates.py のユニットテスト (DIS-C09)"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from check_law_updates import (
    WATCHED_LAWS,
    build_issue_body,
    create_github_issue,
    filter_watched_laws,
    parse_law_updates,
    run,
)

# ─── サンプルXML（e-Gov API v2 モック応答） ──────────────────────────────────

_XML_WITH_TARGET = """\
<?xml version="1.0" encoding="UTF-8"?>
<DataRoot>
  <Result>
    <Code>0</Code>
    <Message>OK</Message>
  </Result>
  <ApplData>
    <LawRevision>
      <LawId>348M50000040005</LawId>
      <LawTitle>企業内容等の開示に関する内閣府令</LawTitle>
      <PromulgationDate>2026-01-15</PromulgationDate>
      <LawTypeName>府令</LawTypeName>
    </LawRevision>
    <LawRevision>
      <LawId>999Z99999999999</LawId>
      <LawTitle>無関係な法令</LawTitle>
      <PromulgationDate>2026-01-10</PromulgationDate>
      <LawTypeName>政令</LawTypeName>
    </LawRevision>
  </ApplData>
</DataRoot>
"""

_XML_NO_MATCH = """\
<?xml version="1.0" encoding="UTF-8"?>
<DataRoot>
  <Result>
    <Code>0</Code>
    <Message>OK</Message>
  </Result>
  <ApplData>
    <LawRevision>
      <LawId>999Z99999999999</LawId>
      <LawTitle>無関係な法令</LawTitle>
      <PromulgationDate>2026-01-10</PromulgationDate>
    </LawRevision>
  </ApplData>
</DataRoot>
"""

_XML_EMPTY = """\
<?xml version="1.0" encoding="UTF-8"?>
<DataRoot>
  <Result>
    <Code>0</Code>
    <Message>OK</Message>
  </Result>
  <ApplData/>
</DataRoot>
"""

_XML_API_ERROR = """\
<?xml version="1.0" encoding="UTF-8"?>
<DataRoot>
  <Result>
    <Code>1</Code>
    <Message>Bad Request</Message>
  </Result>
</DataRoot>
"""


# ─── parse_law_updates ────────────────────────────────────────────────────────

class TestParseLawUpdates:
    def test_parses_law_revision_elements(self):
        updates = parse_law_updates(_XML_WITH_TARGET)
        assert len(updates) == 2

    def test_extracts_law_id(self):
        updates = parse_law_updates(_XML_WITH_TARGET)
        ids = [u["law_id"] for u in updates]
        assert "348M50000040005" in ids

    def test_extracts_law_title(self):
        updates = parse_law_updates(_XML_WITH_TARGET)
        target = next(u for u in updates if u["law_id"] == "348M50000040005")
        assert "企業内容等の開示に関する内閣府令" in target["law_title"]

    def test_extracts_promulgation_date(self):
        updates = parse_law_updates(_XML_WITH_TARGET)
        target = next(u for u in updates if u["law_id"] == "348M50000040005")
        assert target["promulgation_date"] == "2026-01-15"

    def test_empty_appldata_returns_empty_list(self):
        updates = parse_law_updates(_XML_EMPTY)
        assert updates == []

    def test_api_error_returns_empty_list(self):
        updates = parse_law_updates(_XML_API_ERROR)
        assert updates == []

    def test_invalid_xml_returns_empty_list(self):
        updates = parse_law_updates("not xml at all <<<")
        assert updates == []


# ─── filter_watched_laws ─────────────────────────────────────────────────────

class TestFilterWatchedLaws:
    def test_returns_only_watched_laws(self):
        updates = parse_law_updates(_XML_WITH_TARGET)
        matched = filter_watched_laws(updates)
        assert len(matched) == 1
        assert matched[0]["law_id"] == "348M50000040005"

    def test_adds_watched_name(self):
        updates = parse_law_updates(_XML_WITH_TARGET)
        matched = filter_watched_laws(updates)
        assert "watched_name" in matched[0]
        assert "開示府令" in matched[0]["watched_name"]

    def test_no_match_returns_empty(self):
        updates = parse_law_updates(_XML_NO_MATCH)
        matched = filter_watched_laws(updates)
        assert matched == []

    def test_all_watched_law_ids_are_defined(self):
        """WATCHED_LAWS に少なくとも開示府令が含まれることを確認。"""
        assert "348M50000040005" in WATCHED_LAWS

    def test_empty_input_returns_empty(self):
        assert filter_watched_laws([]) == []


# ─── build_issue_body ─────────────────────────────────────────────────────────

class TestBuildIssueBody:
    def _sample_updates(self):
        return [
            {
                "law_id": "348M50000040005",
                "law_title": "企業内容等の開示に関する内閣府令",
                "promulgation_date": "2026-01-15",
                "watched_name": "企業内容等の開示に関する内閣府令（開示府令）",
            }
        ]

    def test_contains_law_id(self):
        body = build_issue_body(self._sample_updates(), date(2026, 1, 1))
        assert "348M50000040005" in body

    def test_contains_since_date(self):
        body = build_issue_body(self._sample_updates(), date(2026, 1, 1))
        assert "2026-01-01" in body

    def test_contains_detected_count(self):
        body = build_issue_body(self._sample_updates(), date(2026, 1, 1))
        assert "1 件" in body

    def test_contains_egov_link(self):
        body = build_issue_body(self._sample_updates(), date(2026, 1, 1))
        assert "laws.e-gov.go.jp" in body

    def test_contains_human_review_warning(self):
        body = build_issue_body(self._sample_updates(), date(2026, 1, 1))
        assert "人間レビュー" in body

    def test_returns_string(self):
        body = build_issue_body(self._sample_updates(), date(2026, 1, 1))
        assert isinstance(body, str)
        assert len(body) > 0


# ─── create_github_issue ──────────────────────────────────────────────────────

class TestCreateGithubIssue:
    def test_returns_issue_url_on_success(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"html_url": "https://github.com/owner/repo/issues/1"}
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            url = create_github_issue(
                token="test_token",
                repo="owner/repo",
                title="Test Issue",
                body="Test body",
            )
        assert url == "https://github.com/owner/repo/issues/1"

    def test_returns_none_on_http_error(self):
        import urllib.error

        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            url="", code=403, msg="Forbidden", hdrs=MagicMock(), fp=MagicMock()
        )):
            url = create_github_issue(
                token="bad_token",
                repo="owner/repo",
                title="Test",
                body="Body",
            )
        assert url is None


# ─── run (統合) ───────────────────────────────────────────────────────────────

class TestRun:
    def test_dry_run_no_match_returns_0(self):
        with patch("check_law_updates.fetch_egov_updates", return_value=_XML_NO_MATCH):
            result = run(date(2026, 1, 1), dry_run=True)
        assert result == 0

    def test_dry_run_with_match_returns_0(self):
        with patch("check_law_updates.fetch_egov_updates", return_value=_XML_WITH_TARGET):
            result = run(date(2026, 1, 1), dry_run=True)
        assert result == 0

    def test_network_error_returns_1(self):
        import urllib.error

        with patch(
            "check_law_updates.fetch_egov_updates",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            result = run(date(2026, 1, 1), dry_run=True)
        assert result == 1

    def test_no_token_with_match_returns_1(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        with patch("check_law_updates.fetch_egov_updates", return_value=_XML_WITH_TARGET):
            result = run(date(2026, 1, 1), dry_run=False)
        assert result == 1
