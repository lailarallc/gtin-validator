from __future__ import annotations

from pydantic import BaseModel


class IssueOut(BaseModel):
    severity: str
    code: str
    message: str
    recommendation: str
    retailer_impact: str


class GTINResultOut(BaseModel):
    raw_input: str
    cleaned: str
    row_number: int
    is_valid: bool
    gtin_type: str
    issues: list[IssueOut]
    corrected_value: str | None
    company_prefix: str | None
    indicator_digit: str | None
    check_digit_expected: str | None
    has_critical: bool
    has_warning: bool


class BatchSummaryOut(BaseModel):
    total_gtins: int
    valid: int
    critical_issues: int
    warnings: int
    clean: int
    duplicate_groups: int
    unique_prefixes: int


class ScoreResultOut(BaseModel):
    score: int
    grade: str
    interpretation: str


class CostEstimateOut(BaseModel):
    chargeback_range: tuple[int, int]
    delayed_launch_range: tuple[int, int]
    rework_hours: int
    rework_cost: int
    annual_estimate_low: int
    annual_estimate_high: int
    growth_note: str
    delayed_skus: int
    # The assumptions behind the totals (editable in the report) and the
    # driver counts they multiply, so the figures read as adjustable, not fact.
    assumptions: dict[str, float]
    drivers: dict[str, int]


class HierarchyPairOut(BaseModel):
    case_gtin: str
    case_row: int
    unit_gtin: str
    unit_row: int
    indicator: str


class HierarchyOut(BaseModel):
    matched_pairs: list[HierarchyPairOut]
    orphan_cases: list[GTINResultOut]
    units_without_cases: list[GTINResultOut]
    has_hierarchy: bool
    hierarchy_complete: bool


class RetailerCheckOut(BaseModel):
    check: str
    passed: bool
    detail: str
    failing_gtins: list[tuple[int, str]]


class RetailerChecklistOut(BaseModel):
    profile: dict
    checks: list[RetailerCheckOut]
    passed: int
    total: int
    ready: bool


class BeforeAfterOut(BaseModel):
    row: int
    before: str
    after: str
    issue: str


class FixRoadmapItemOut(BaseModel):
    priority: int
    code: str
    action: str
    count: int
    severity: str
    effort: str
    effort_detail: str
    impact: str
    impact_detail: str
    time_estimate: str


class GTIN14IndicatorOut(BaseModel):
    gtin14: str
    label: str


class GTIN14SuggestionOut(BaseModel):
    row: int
    unit_gtin: str
    unit_type: str
    indicators: dict[int, GTIN14IndicatorOut]


class FieldAnalysisOut(BaseModel):
    column_name: str
    total_rows: int
    populated: int
    missing: int
    completeness_pct: float


class RetailerDataGapOut(BaseModel):
    required: int
    present: int
    missing_fields: list[str]
    incomplete_fields: list[str]
    ready: bool


class DataCompletenessOut(BaseModel):
    field_analysis: dict[str, FieldAnalysisOut]
    missing_important_fields: list[str]
    retailer_data_gaps: dict[str, RetailerDataGapOut]
    overall_completeness: float


class ValidationResponse(BaseModel):
    token: str
    results: list[GTINResultOut]
    summary: BatchSummaryOut
    duplicates: dict[str, int]
    hierarchy: HierarchyOut
    retailer_checklists: dict[str, RetailerChecklistOut]
    score: ScoreResultOut
    cost_estimate: CostEstimateOut | None
    executive_summary: str
    fix_roadmap: list[FixRoadmapItemOut]
    before_after: list[BeforeAfterOut]
    gtin14_suggestions: list[GTIN14SuggestionOut]


class SummaryResponse(BaseModel):
    """Own-data result: score and issue counts only. No rows, no token."""

    summary: BatchSummaryOut
    score: ScoreResultOut


class UploadColumnsResponse(BaseModel):
    columns: list[str]
    detected_gtin_column: str | None
    row_count: int
    preview: list[dict[str, str | None]]


class SampleDataResponse(BaseModel):
    csv: str
    description: str
