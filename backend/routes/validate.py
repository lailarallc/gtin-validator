from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Request, UploadFile

from backend.cache import get_result, store_result
from backend.limiter import limiter
from backend.schemas.requests import ValidateTextRequest
from backend.schemas.responses import (
    BatchSummaryOut,
    DataCompletenessOut,
    FieldAnalysisOut,
    RetailerDataGapOut,
    ScoreResultOut,
    SummaryResponse,
    ValidationResponse,
)
from backend.serializers import serialize_batch_result
from gtin_core import (
    check_data_completeness,
    generate_before_after,
    generate_executive_summary,
    generate_fix_roadmap,
    generate_gtin14_suggestions,
    split_gtin_entries,
    validate_batch,
)
from sample_data import SAMPLE_DATA

router = APIRouter()

GTIN_KEYWORDS = ["gtin", "upc", "ean", "barcode", "code", "item number", "sku"]
MAX_GTINS = 10_000
MAX_FILE_BYTES = 10 * 1024 * 1024


def _detect_gtin_column(df: pd.DataFrame, override: str | None = None) -> str:
    if override and override in df.columns:
        return override
    for col in df.columns:
        if any(term in str(col).lower() for term in GTIN_KEYWORDS):
            return str(col)
    return str(df.columns[0])


def _run_validation(gtins: list[str], df: pd.DataFrame | None = None) -> tuple[dict, str]:
    if len(gtins) > MAX_GTINS:
        gtins = gtins[:MAX_GTINS]

    validation_data = validate_batch(gtins)

    executive_summary = generate_executive_summary(validation_data)
    fix_roadmap = generate_fix_roadmap(
        validation_data["results"], validation_data["hierarchy"]
    )
    before_after = generate_before_after(validation_data["results"])
    gtin14_suggestions = generate_gtin14_suggestions(
        validation_data["results"], validation_data["hierarchy"]
    )

    token = store_result(validation_data, df)

    response_data = serialize_batch_result(
        validation_data,
        executive_summary=executive_summary,
        fix_roadmap=fix_roadmap,
        before_after=before_after,
        gtin14_suggestions=gtin14_suggestions,
        token=token,
    )
    return response_data, token


def _run_summary(gtins: list[str]) -> SummaryResponse:
    """Own-data path: score and counts only. Nothing is cached, no token issued."""
    validation_data = validate_batch(gtins[:MAX_GTINS])
    return SummaryResponse(
        summary=BatchSummaryOut(**validation_data["summary"]),
        score=ScoreResultOut(**validation_data["score"]),
    )


def _sample_gtins() -> list[str]:
    """Take the GTIN column from SAMPLE_DATA the way the frontend parsed it."""
    lines = SAMPLE_DATA.strip().split("\n")
    columns = [c.strip() for c in lines[0].split(",")]
    idx = columns.index("GTIN")
    gtins = []
    for line in lines[1:]:
        values = line.split(",")
        value = values[idx].strip() if idx < len(values) else ""
        if value:
            gtins.append(value)
    return gtins


@router.post(
    "/sample/validate",
    response_model=ValidationResponse,
    responses={429: {"description": "Rate limit exceeded"}},
)
@limiter.limit("10/minute")
def validate_sample(request: Request) -> dict:
    response_data, _ = _run_validation(_sample_gtins())
    return response_data


@router.post("/validate", response_model=SummaryResponse, responses={429: {"description": "Rate limit exceeded"}})
@limiter.limit("10/minute")
def validate_text(request: Request, body: ValidateTextRequest) -> SummaryResponse:
    gtins = split_gtin_entries(body.gtins)
    if not gtins:
        raise HTTPException(400, "No GTINs provided.")
    return _run_summary(gtins)


@router.post(
    "/validate/upload",
    response_model=SummaryResponse,
    responses={429: {"description": "Rate limit exceeded"}},
)
@limiter.limit("10/minute")
def validate_upload(
    request: Request,
    file: UploadFile,
    gtin_column: str | None = None,
) -> SummaryResponse:
    if not file.filename:
        raise HTTPException(400, "No file provided.")

    content = file.file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 10 MB limit.")

    ext = Path(file.filename).suffix.lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(BytesIO(content), dtype=str)
        elif ext == ".csv":
            df = pd.read_csv(BytesIO(content), dtype=str)
        else:
            raise HTTPException(400, "Unsupported file type. Upload CSV or Excel.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Could not read file. Please upload a valid CSV or Excel file.")

    if df.empty:
        raise HTTPException(400, "File is empty.")

    col = _detect_gtin_column(df, gtin_column)
    gtins = [g for g in df[col].fillna("").astype(str).tolist() if g.strip()]
    if not gtins:
        raise HTTPException(400, f"No GTINs found in column '{col}'.")

    return _run_summary(gtins)


@router.get("/completeness/{token}")
def get_completeness(token: str) -> DataCompletenessOut:
    entry = get_result(token)
    if entry is None:
        raise HTTPException(404, "Validation result expired or not found.")
    if entry.dataframe is None:
        raise HTTPException(400, "No file data available for completeness analysis.")

    if len(entry.dataframe.columns) <= 1:
        raise HTTPException(
            400, "File has only one column — completeness analysis needs additional product data columns."
        )

    completeness = check_data_completeness(entry.dataframe)

    return DataCompletenessOut(
        field_analysis={
            name: FieldAnalysisOut(**data)
            for name, data in completeness["field_analysis"].items()
        },
        missing_important_fields=completeness["missing_important_fields"],
        retailer_data_gaps={
            retailer: RetailerDataGapOut(**gaps)
            for retailer, gaps in completeness["retailer_data_gaps"].items()
        },
        overall_completeness=completeness["overall_completeness"],
    )
