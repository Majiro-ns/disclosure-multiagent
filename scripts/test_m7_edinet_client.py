"""
tests/test_m7_edinet_client.py
================================
disclosure-multiagent M7-1 EDINET クライアントのテスト

全テストは USE_MOCK_EDINET=true で動作（ネット接続・Subscription-Key 不要）。

TC-1:  validate_edinetcode — 正常値（E + 5桁）
TC-2:  validate_edinetcode — E なし → False
TC-3:  validate_edinetcode — 桁数不足 → False
TC-4:  validate_edinetcode — 大文字以外 → False
TC-5:  validate_doc_id — 正常値（S + 7桁英数字）
TC-6:  validate_doc_id — S 以外の先頭文字 → False
TC-7:  validate_doc_id — 長さ不正 → False
TC-8:  fetch_document_list — モック: docTypeCode=120 のみ返る
TC-9:  fetch_document_list — モック: 別種別コード → 空リスト
TC-10: fetch_document_list — 実API・キーなし → RuntimeError
TC-11: download_pdf — モック: 既存サンプルPDFパスを返す
TC-12: download_pdf — 不正 doc_id → ValueError
TC-13: search_by_company — モック: 部分一致
TC-14: search_by_company — モック: 不一致 → 空リスト
TC-15: MOCK_DOCUMENTS の件数・フィールド確認
TC-16: REQUEST_DELAY — 定数が 3.0 秒以上
TC-17: BatchCompanyResult — フィールド・success プロパティ確認
TC-18: batch_fetch_companies — モック 3社（全ヒット）
TC-19: batch_fetch_companies — モック 一致なし企業含む混在
TC-20: batch_fetch_companies — 空リスト入力 → 空リスト返す
TC-21: batch_fetch_companies — 入力順保持
TC-22: batch_fetch_companies — company_name/year フィールド確認
"""
import os
import pytest

# テスト実行時は常にモックモード
os.environ["USE_MOCK_EDINET"] = "true"
os.environ.pop("EDINET_SUBSCRIPTION_KEY", None)

from m7_edinet_client import (
    MOCK_DOCUMENTS,
    REQUEST_DELAY,
    BatchCompanyResult,
    batch_fetch_companies,
    download_pdf,
    fetch_document_list,
    search_by_company,
    validate_doc_id,
    validate_edinetcode,
)


# ── TC-1〜4: validate_edinetcode ───────────────────────────────────────────

def test_tc1_edinetcode_valid():
    """正常値: E + 5桁数字"""
    assert validate_edinetcode("E01234") is True
    assert validate_edinetcode("E99999") is True


def test_tc2_edinetcode_no_e():
    """E が先頭にない → False"""
    assert validate_edinetcode("012345") is False
    assert validate_edinetcode("A01234") is False


def test_tc3_edinetcode_short():
    """桁数不足（E + 4桁）→ False"""
    assert validate_edinetcode("E0123") is False


def test_tc4_edinetcode_extra_chars():
    """E + 5桁 + 余分な文字 → False"""
    assert validate_edinetcode("E012345") is False
    assert validate_edinetcode("E0123X") is False


# ── TC-5〜7: validate_doc_id ──────────────────────────────────────────────

def test_tc5_doc_id_valid():
    """正常値: S + 7桁英数字"""
    assert validate_doc_id("S100A001") is True
    assert validate_doc_id("S1234567") is True
    assert validate_doc_id("SABCDEFG") is True


def test_tc6_doc_id_wrong_prefix():
    """S 以外の先頭文字 → False"""
    assert validate_doc_id("X100A001") is False
    assert validate_doc_id("s100A001") is False  # 小文字も不可


def test_tc7_doc_id_wrong_length():
    """桁数不正 → False"""
    assert validate_doc_id("S100A00") is False   # 7文字（S含め8文字必要）
    assert validate_doc_id("S100A0012") is False  # 9文字（多すぎ）


# ── TC-8〜10: fetch_document_list ─────────────────────────────────────────

def test_tc8_fetch_document_list_mock_returns_120():
    """モック: docTypeCode=120 のみ返る"""
    docs = fetch_document_list("2026-01-10")
    assert len(docs) > 0
    assert all(d["docTypeCode"] == "120" for d in docs)


def test_tc9_fetch_document_list_mock_other_type():
    """モック: 存在しない書類種別 → 空リスト"""
    docs = fetch_document_list("2026-01-10", doc_type_code="999")
    assert docs == []


def test_tc10_fetch_document_list_real_api_no_key(monkeypatch):
    """実API・Subscription-Key なし → RuntimeError"""
    monkeypatch.setenv("USE_MOCK_EDINET", "false")
    # モジュールの USE_MOCK_EDINET をパッチ
    import m7_edinet_client as m7
    monkeypatch.setattr(m7, "USE_MOCK_EDINET", False)
    monkeypatch.setattr(m7, "SUBSCRIPTION_KEY", "")
    with pytest.raises(RuntimeError, match="Subscription-Key"):
        m7.fetch_document_list("2026-01-10")


# ── TC-11〜12: download_pdf ───────────────────────────────────────────────

def test_tc11_download_pdf_mock_returns_existing_file():
    """モック: 既存 company_a.pdf のパスを返す"""
    path = download_pdf("S100A001", "/tmp/test_edinet_out")
    assert path.endswith(".pdf")
    import os
    assert os.path.exists(path)


def test_tc12_download_pdf_invalid_doc_id():
    """不正な doc_id → ValueError"""
    with pytest.raises(ValueError, match="無効な書類管理番号"):
        download_pdf("INVALID!", "/tmp/test_edinet_out")
    with pytest.raises(ValueError, match="無効な書類管理番号"):
        download_pdf("X100A001", "/tmp/test_edinet_out")


# ── TC-13〜14: search_by_company ─────────────────────────────────────────

def test_tc13_search_by_company_mock_partial_match():
    """モック: 部分一致でヒット"""
    results = search_by_company("サンプル社A", 2023)
    assert len(results) >= 1
    assert all("サンプル社A" in d["filerName"] for d in results)


def test_tc14_search_by_company_mock_no_match():
    """モック: 一致なし → 空リスト"""
    results = search_by_company("存在しない会社XYZ", 2023)
    assert results == []


# ── TC-15: MOCK_DOCUMENTS 構造確認 ────────────────────────────────────────

def test_tc15_mock_documents_structure():
    """MOCK_DOCUMENTS の件数・必須フィールド確認"""
    assert len(MOCK_DOCUMENTS) >= 2
    required_keys = {"docID", "edinetCode", "filerName", "docTypeCode", "periodEnd"}
    for doc in MOCK_DOCUMENTS:
        assert required_keys.issubset(doc.keys()), f"フィールド不足: {doc}"
        assert validate_edinetcode(doc["edinetCode"]), f"EDINETコード形式不正: {doc['edinetCode']}"
        assert validate_doc_id(doc["docID"]), f"書類管理番号形式不正: {doc['docID']}"


# ── TC-16〜22: REQUEST_DELAY / BatchCompanyResult / batch_fetch_companies ──

def test_tc16_request_delay_ge_3():
    """REQUEST_DELAY 定数が 3.0 秒以上（DOS対策要件）"""
    assert REQUEST_DELAY >= 3.0


def test_tc17_batch_company_result_fields():
    """BatchCompanyResult フィールド・success プロパティの動作確認"""
    # 書類あり・エラーなし → success=True
    r_ok = BatchCompanyResult(
        company_name="テスト社", year=2023,
        docs=[{"docID": "S100A001"}], downloaded_paths=[]
    )
    assert r_ok.success is True

    # 書類ゼロ → success=False
    r_empty = BatchCompanyResult(company_name="テスト社", year=2023, docs=[])
    assert r_empty.success is False

    # エラーあり → success=False
    r_err = BatchCompanyResult(
        company_name="テスト社", year=2023,
        docs=[{"docID": "S100A001"}], error="接続失敗"
    )
    assert r_err.success is False


def test_tc18_batch_fetch_companies_mock_3_companies():
    """モック: 3社指定・全社ヒット → BatchCompanyResult リスト返却"""
    companies = [
        {"company_name": "サンプル社A", "year": 2023},
        {"company_name": "サンプル社B", "year": 2023},
        {"company_name": "サンプル社C", "year": 2023},
    ]
    results = batch_fetch_companies(companies)
    assert len(results) == 3
    for r in results:
        assert isinstance(r, BatchCompanyResult)
        assert len(r.docs) >= 1, f"{r.company_name} の書類が0件"
        assert r.error == ""
        assert r.success is True


def test_tc19_batch_fetch_companies_mixed():
    """モック: ヒットあり企業・ヒットなし企業の混在"""
    companies = [
        {"company_name": "サンプル社A", "year": 2023},
        {"company_name": "存在しない会社XYZ", "year": 2023},
        {"company_name": "サンプル社B", "year": 2023},
    ]
    results = batch_fetch_companies(companies)
    assert len(results) == 3

    assert results[0].company_name == "サンプル社A"
    assert results[0].success is True

    assert results[1].company_name == "存在しない会社XYZ"
    assert results[1].docs == []
    assert results[1].success is False
    assert results[1].error == ""  # エラーではなく単に0件

    assert results[2].company_name == "サンプル社B"
    assert results[2].success is True


def test_tc20_batch_fetch_companies_empty_input():
    """空リスト入力 → 空リスト返す"""
    results = batch_fetch_companies([])
    assert results == []


def test_tc21_batch_fetch_companies_order_preserved():
    """入力順が出力順に保持されること"""
    companies = [
        {"company_name": "サンプル社C", "year": 2023},
        {"company_name": "サンプル社A", "year": 2023},
        {"company_name": "サンプル社B", "year": 2023},
    ]
    results = batch_fetch_companies(companies)
    assert len(results) == 3
    assert results[0].company_name == "サンプル社C"
    assert results[1].company_name == "サンプル社A"
    assert results[2].company_name == "サンプル社B"


def test_tc22_batch_fetch_companies_year_field():
    """BatchCompanyResult の year フィールドが入力値と一致"""
    companies = [
        {"company_name": "サンプル社A", "year": 2022},
        {"company_name": "サンプル社B", "year": 2024},
    ]
    results = batch_fetch_companies(companies)
    assert results[0].year == 2022
    assert results[1].year == 2024
