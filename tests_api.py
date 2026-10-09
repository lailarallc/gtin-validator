"""API endpoint tests for the FastAPI backend."""

import csv
import uuid
from io import StringIO

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app

VALID_GTINS = ["614141000012", "614141000029", "614141000036"]
INVALID_GTIN = "614141000019"  # bad check digit


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    @pytest.mark.anyio
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Sample data + retailers
# ---------------------------------------------------------------------------


class TestSampleAndRetailers:
    @pytest.mark.anyio
    async def test_sample_data(self, client):
        resp = await client.get("/api/sample")
        assert resp.status_code == 200
        data = resp.json()
        assert "csv" in data
        assert "description" in data
        assert "GTIN" in data["csv"]

    @pytest.mark.anyio
    async def test_retailers(self, client):
        resp = await client.get("/api/retailers")
        assert resp.status_code == 200
        data = resp.json()
        assert "Walmart" in data
        assert "description" in data["Walmart"]


# ---------------------------------------------------------------------------
# Validation — text input
# ---------------------------------------------------------------------------


class TestValidateText:
    @pytest.mark.anyio
    async def test_own_data_is_summary_only(self, client):
        resp = await client.post("/api/validate", json={"gtins": VALID_GTINS})
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"summary", "score"}
        assert data["summary"]["total_gtins"] == 3
        assert data["score"]["grade"] in ("A", "B", "C", "D", "F", "N/A")

    @pytest.mark.anyio
    async def test_invalid_gtin_counted(self, client):
        resp = await client.post("/api/validate", json={"gtins": [INVALID_GTIN]})
        assert resp.status_code == 200
        assert resp.json()["summary"]["critical_issues"] == 1

    @pytest.mark.anyio
    async def test_empty_list_rejected(self, client):
        resp = await client.post("/api/validate", json={"gtins": []})
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_gtins_on_one_line_counted_separately(self, client):
        resp = await client.post(
            "/api/validate", json={"gtins": ["614141000012 614141000019, 12345"]}
        )
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert summary["total_gtins"] == 3
        assert summary["critical_issues"] == 2

    @pytest.mark.anyio
    async def test_blank_entries_rejected(self, client):
        resp = await client.post("/api/validate", json={"gtins": ["", "  "]})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Validation — sample data (the only path that returns the full report)
# ---------------------------------------------------------------------------


class TestValidateSample:
    @pytest.mark.anyio
    async def test_sample_full_response(self, client):
        resp = await client.post("/api/sample/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"]
        assert data["score"]["score"] == 82
        assert data["score"]["grade"] == "B"
        # Same summary locked in test_golden.py
        assert data["summary"] == {
            "total_gtins": 46,
            "valid": 40,
            "critical_issues": 6,
            "warnings": 4,
            "clean": 36,
            "duplicate_groups": 2,
            "unique_prefixes": 3,
        }
        assert len(data["results"]) == 46
        assert isinstance(data["executive_summary"], str)
        assert isinstance(data["fix_roadmap"], list)
        assert isinstance(data["before_after"], list)
        assert isinstance(data["gtin14_suggestions"], list)
        assert "checks" in data["retailer_checklists"]["Walmart"]
        assert "matched_pairs" in data["hierarchy"]
        assert data["cost_estimate"] is not None


# ---------------------------------------------------------------------------
# Validation — file upload
# ---------------------------------------------------------------------------


class TestValidateUpload:
    @pytest.mark.anyio
    async def test_csv_upload(self, client):
        csv_content = "GTIN,Product\n614141000012,Test Product\n614141000029,Another Product\n"
        files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
        resp = await client.post("/api/validate/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"summary", "score"}
        assert data["summary"]["total_gtins"] == 2

    @pytest.mark.anyio
    async def test_csv_upload_auto_detect_column(self, client):
        csv_content = "SKU,UPC Code,Name\n1,614141000012,Widget\n2,614141000029,Gadget\n"
        files = {"file": ("items.csv", csv_content.encode(), "text/csv")}
        resp = await client.post("/api/validate/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_gtins"] == 2

    @pytest.mark.anyio
    async def test_unsupported_file_type(self, client):
        files = {"file": ("data.json", b'{"gtins":[]}', "application/json")}
        resp = await client.post("/api/validate/upload", files=files)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_column_override(self, client):
        csv_content = "ID,Barcode,Name\n1,614141000012,Widget\n2,614141000029,Gadget\n"
        files = {"file": ("items.csv", csv_content.encode(), "text/csv")}
        resp = await client.post(
            "/api/validate/upload", files=files, params={"gtin_column": "Barcode"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_gtins"] == 2


# ---------------------------------------------------------------------------
# Report downloads
# ---------------------------------------------------------------------------


class TestReports:
    @pytest.fixture
    async def token(self, client):
        resp = await client.post("/api/sample/validate")
        return resp.json()["token"]

    @pytest.mark.anyio
    async def test_csv_report(self, client, token):
        resp = await client.get(f"/api/reports/csv/{token}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        reader = csv.reader(StringIO(resp.text))
        header = next(reader)
        assert "GTIN (Original)" in header

    @pytest.mark.anyio
    async def test_corrected_csv(self, client, token):
        resp = await client.get(f"/api/reports/corrected/{token}")
        assert resp.status_code == 200
        reader = csv.reader(StringIO(resp.text))
        header = next(reader)
        assert "Corrected GTIN" in header

    @pytest.mark.anyio
    async def test_pdf_report(self, client, token):
        resp = await client.get(f"/api/reports/pdf/{token}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"

    @pytest.mark.anyio
    async def test_pdf_with_company_name(self, client, token):
        resp = await client.get(
            f"/api/reports/pdf/{token}", params={"company_name": "Acme Foods"}
        )
        assert resp.status_code == 200
        assert "Acme_Foods" in resp.headers.get("content-disposition", "")

    @pytest.mark.anyio
    async def test_expired_token(self, client):
        resp = await client.get("/api/reports/csv/nonexistent_token")
        assert resp.status_code == 404

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "path",
        [
            "/api/reports/csv/{t}",
            "/api/reports/corrected/{t}",
            "/api/reports/pdf/{t}",
            "/api/completeness/{t}",
        ],
    )
    async def test_non_sample_token_404(self, client, path):
        # Own-data calls issue no token, so any token not from the sample
        # endpoint (well-formed or not) must 404 on every report endpoint.
        await client.post("/api/validate", json={"gtins": VALID_GTINS})
        for t in ("not-a-token", uuid.uuid4().hex):
            resp = await client.get(path.format(t=t))
            assert resp.status_code == 404
            assert resp.json() == {"detail": "Validation result expired or not found."}


# ---------------------------------------------------------------------------
# Data completeness
# ---------------------------------------------------------------------------


class TestCompleteness:
    @pytest.mark.anyio
    async def test_completeness_sample_has_no_file_data(self, client):
        # The sample is validated from its GTIN column only, as before, so
        # there is no product data to analyze.
        token = (await client.post("/api/sample/validate")).json()["token"]
        resp = await client.get(f"/api/completeness/{token}")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_completeness_expired_token(self, client):
        resp = await client.get("/api/completeness/nonexistent")
        assert resp.status_code == 404
