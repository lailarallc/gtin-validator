"""
GTIN Validator — Core Validation Engine

Validates GTINs against GS1 standards with retailer-context diagnostics.
Designed for specialty food brands preparing product data for national
retail submission (Walmart, Costco, UNFI, 1WorldSync, and more).

References:
    - GS1 General Specifications §7.9 (check digit algorithm)
    - GS1 US GTIN Allocation Rules
    - Walmart Item 360 Product Identifiers
    - 1WorldSync GDSN requirements
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypedDict

import pandas as pd

# =============================================================================
# Data models
# =============================================================================

class Severity(Enum):
    """Issue severity levels, ordered by impact on retailer submissions."""
    CRITICAL = "Critical"
    WARNING = "Warning"
    INFO = "Info"


class GTINType(Enum):
    """Standard GTIN formats recognized by GS1."""
    GTIN_8 = "GTIN-8"
    GTIN_12 = "GTIN-12 (UPC-A)"
    GTIN_13 = "GTIN-13 (EAN)"
    GTIN_14 = "GTIN-14 (ITF-14)"
    UNKNOWN = "Unknown"


@dataclass
class Issue:
    """A single validation issue found on a GTIN."""
    severity: Severity
    code: str
    message: str
    recommendation: str
    retailer_impact: str


@dataclass
class GTINResult:
    """Complete validation result for a single GTIN."""
    raw_input: str
    cleaned: str
    row_number: int
    is_valid: bool
    gtin_type: GTINType
    issues: list[Issue] = field(default_factory=list)
    corrected_value: Optional[str] = None
    company_prefix: Optional[str] = None
    indicator_digit: Optional[str] = None
    check_digit_expected: Optional[str] = None

    @property
    def has_critical(self) -> bool:
        """True if any issue is severity CRITICAL."""
        return any(i.severity == Severity.CRITICAL for i in self.issues)

    @property
    def has_warning(self) -> bool:
        """True if any issue is severity WARNING."""
        return any(i.severity == Severity.WARNING for i in self.issues)


# =============================================================================
# Check digit calculation (GS1 mod-10 algorithm)
# =============================================================================

def calculate_check_digit(digits: str) -> int:
    """
    Calculate a GS1 standard check digit using the mod-10 algorithm.

    Works for GTIN-8, GTIN-12, GTIN-13, and GTIN-14.

    Args:
        digits: All digits EXCEPT the check digit (i.e., N-1 digits).

    Returns:
        The expected check digit (0-9).

    Reference:
        GS1 General Specifications §7.9.1
    """
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(reversed(digits))
    )
    return (10 - total % 10) % 10


def identify_gtin_type(length: int) -> GTINType:
    """Map a digit count to the corresponding GTIN format."""
    return {
        8: GTINType.GTIN_8,
        12: GTINType.GTIN_12,
        13: GTINType.GTIN_13,
        14: GTINType.GTIN_14,
    }.get(length, GTINType.UNKNOWN)


class BatchSummary(TypedDict):
    total_gtins: int
    valid: int
    critical_issues: int
    warnings: int
    clean: int
    duplicate_groups: int
    unique_prefixes: int


class ScoreResult(TypedDict):
    score: int
    grade: str
    interpretation: str


class BatchResult(TypedDict):
    results: list[GTINResult]
    summary: BatchSummary
    duplicates: dict[str, int]
    hierarchy: dict
    retailer_checklists: dict
    score: ScoreResult
    cost_estimate: dict


# =============================================================================
# Retailer requirement profiles
# =============================================================================

RETAILER_PROFILES: dict[str, dict] = {
    "Walmart": {
        "description": "Walmart Item 360 / Retail Link",
        "required_gtin_types": [GTINType.GTIN_12, GTINType.GTIN_14],
        "requires_hierarchy": True,
        "requires_case_gtin": True,
        "notes": (
            "Walmart requires GTINs at every packaging level (each, inner pack, "
            "case, pallet). All GTINs are validated against the GS1 database. "
            "Items with invalid GTINs will not go live in Item 360."
        ),
    },
    "Costco": {
        "description": "Costco Item Setup Workbook",
        "required_gtin_types": [GTINType.GTIN_12, GTINType.GTIN_13, GTINType.GTIN_14],
        "requires_hierarchy": True,
        "requires_case_gtin": True,
        "notes": (
            "Costco requires valid GTINs for all items. Dimension and weight "
            "discrepancies tied to wrong GTINs result in logistics chargebacks."
        ),
    },
    "UNFI": {
        "description": "UNFI New Item Form",
        "required_gtin_types": [GTINType.GTIN_12, GTINType.GTIN_13, GTINType.GTIN_14],
        "requires_hierarchy": False,
        "requires_case_gtin": True,
        "notes": (
            "UNFI requires UPC for each sellable unit. Case GTIN needed for "
            "warehouse receiving. Incorrect GTINs delay item activation."
        ),
    },
    "Whole Foods": {
        "description": "Whole Foods Market Item Setup",
        "required_gtin_types": [GTINType.GTIN_12, GTINType.GTIN_13],
        "requires_hierarchy": False,
        "requires_case_gtin": False,
        "notes": (
            "Whole Foods requires valid UPC/EAN for each sellable unit. Items "
            "synced via 1WorldSync must have complete, accurate data."
        ),
    },
    "KeHE": {
        "description": "KeHE Distributors Item Setup",
        "required_gtin_types": [GTINType.GTIN_12, GTINType.GTIN_13, GTINType.GTIN_14],
        "requires_hierarchy": False,
        "requires_case_gtin": True,
        "notes": (
            "KeHE requires UPC for each sellable unit and case GTIN for "
            "warehouse operations. Data synced via 1WorldSync."
        ),
    },
    "1WorldSync (GDSN)": {
        "description": "1WorldSync Global Data Synchronisation Network",
        "required_gtin_types": [GTINType.GTIN_12, GTINType.GTIN_13, GTINType.GTIN_14],
        "requires_hierarchy": True,
        "requires_case_gtin": True,
        "notes": (
            "1WorldSync is the industry data pool. Wrong data here propagates "
            "to every retailer pulling from it. Wrong dimensions cause pallet "
            "configuration errors and logistics chargebacks. Wrong nutritional "
            "data creates legal exposure."
        ),
    },
}


# =============================================================================
# Single-GTIN validation
# =============================================================================

def validate_single_gtin(raw: str, row_number: int) -> GTINResult:
    """
    Validate a single GTIN string against GS1 standards.

    Checks performed (in order):
        1. Empty / blank
        2. Non-numeric characters
        3. Valid length (8, 12, 13, or 14 digits)
        4. Check digit (mod-10)
        5. GTIN-14 indicator digit rules
        6. All-zeros placeholder detection
        7. UPC-A → GTIN-13 format advisory

    Args:
        raw: The raw GTIN string as entered by the user.
        row_number: 1-based row position in the input file.

    Returns:
        A GTINResult with all issues found.
    """
    if not isinstance(raw, str):
        raw = "" if raw is None or (isinstance(raw, float) and raw != raw) else str(raw)
    cleaned = raw.strip().replace("-", "").replace(" ", "")
    result = GTINResult(
        raw_input=raw.strip(),
        cleaned=cleaned,
        row_number=row_number,
        is_valid=True,
        gtin_type=GTINType.UNKNOWN,
    )

    # --- Empty check ---
    if not cleaned:
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="EMPTY",
            message="GTIN is empty or blank.",
            recommendation="Provide a valid GTIN for this item.",
            retailer_impact="No retailer will accept an item without a GTIN.",
        ))
        return result

    # --- Numeric check ---
    if not cleaned.isdigit():
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="NON_NUMERIC",
            message=f"GTIN contains non-numeric characters: '{cleaned}'.",
            recommendation="Remove all letters, symbols, and spaces. GTINs are numeric only.",
            retailer_impact="All retailer systems will reject a non-numeric GTIN.",
        ))
        return result

    # --- Length / type check ---
    gtin_type = identify_gtin_type(len(cleaned))
    result.gtin_type = gtin_type

    if gtin_type == GTINType.UNKNOWN:
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="INVALID_LENGTH",
            message=f"GTIN has {len(cleaned)} digits. Valid lengths are 8, 12, 13, or 14.",
            recommendation=(
                "Check if digits were truncated or extra digits added. "
                "UPC-A is 12 digits, EAN is 13 digits, ITF-14 is 14 digits."
            ),
            retailer_impact="No retailer system will recognize a GTIN with this length.",
        ))
        return result

    # --- Check digit validation ---
    payload = cleaned[:-1]
    actual_check = int(cleaned[-1])
    expected_check = calculate_check_digit(payload)
    result.check_digit_expected = str(expected_check)

    if actual_check != expected_check:
        result.is_valid = False
        corrected = payload + str(expected_check)
        result.corrected_value = corrected
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="BAD_CHECK_DIGIT",
            message=(
                f"Check digit is {actual_check}, but should be {expected_check}. "
                f"Corrected GTIN would be {corrected}."
            ),
            recommendation=(
                "This usually means a digit was mistyped or the GTIN was "
                "manually constructed incorrectly. Verify against the original "
                "barcode or GS1 registration."
            ),
            retailer_impact=(
                "Walmart, Costco, and 1WorldSync all validate check digits. "
                "This GTIN will be rejected on submission."
            ),
        ))

    # --- GTIN-14 indicator digit checks ---
    if gtin_type == GTINType.GTIN_14:
        indicator = cleaned[0]
        result.indicator_digit = indicator
        if indicator == "0":
            result.issues.append(Issue(
                severity=Severity.INFO,
                code="INDICATOR_ZERO",
                message=(
                    "GTIN-14 has indicator digit 0, which means this is a "
                    "base unit (each) expressed in 14-digit format."
                ),
                recommendation="This is valid but confirm it's not meant to be a case-level GTIN.",
                retailer_impact="Some systems may expect GTIN-12 or GTIN-13 for eaches.",
            ))
        elif indicator == "9":
            result.issues.append(Issue(
                severity=Severity.WARNING,
                code="INDICATOR_NINE",
                message="GTIN-14 has indicator digit 9, reserved for variable measure items.",
                recommendation=(
                    "Variable measure GTINs are for items sold by weight or volume. "
                    "If this is a fixed-weight consumer product, the indicator digit is wrong."
                ),
                retailer_impact=(
                    "Retailers handle variable measure items differently. "
                    "Using indicator 9 on a fixed item will cause processing errors."
                ),
            ))
        elif indicator in "12345678":
            result.issues.append(Issue(
                severity=Severity.INFO,
                code="CASE_LEVEL",
                message=(
                    f"GTIN-14 with indicator digit {indicator} — this identifies "
                    f"a packaging level (case/inner pack/pallet)."
                ),
                recommendation="Verify this GTIN corresponds to the correct packaging level in your hierarchy.",
                retailer_impact="Walmart requires unique GTINs at each packaging level.",
            ))

    # --- All-zeros check ---
    if cleaned == "0" * len(cleaned):
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="ALL_ZEROS",
            message="GTIN is all zeros — this is a placeholder, not a real GTIN.",
            recommendation="Replace with a valid GTIN from your GS1 registration.",
            retailer_impact="No retailer will accept an all-zero GTIN.",
        ))

    # --- UPC-A (GTIN-12) submitted where GTIN-13 may be expected ---
    if gtin_type == GTINType.GTIN_12:
        result.issues.append(Issue(
            severity=Severity.INFO,
            code="UPC_NOT_GTIN13",
            message=(
                "This is a 12-digit UPC-A. Some systems require the 13-digit "
                "GTIN-13 format (with a leading zero). Your GTIN-13 equivalent "
                f"would be 0{cleaned}."
            ),
            recommendation=(
                "1WorldSync, European retailers, and some data pools expect "
                "GTIN-13 format. Verify which format your trading partner "
                "requires. To convert, add a leading zero."
            ),
            retailer_impact=(
                "1WorldSync GDSN requires GTIN-13 or GTIN-14 format. Submitting "
                "a 12-digit UPC may be rejected or require manual conversion. "
                "Costco's international operations also expect GTIN-13."
            ),
        ))

    # --- Extract company prefix (approximate — real prefix length varies 7-10) ---
    # All types are sliced from the 13-digit (GTIN-13-normalized) form so a
    # UPC-A and its case-level GTIN-14 yield the same prefix.
    if gtin_type == GTINType.GTIN_12:
        result.company_prefix = ("0" + cleaned)[:7]  # zero-pad to GTIN-13 form
    elif gtin_type == GTINType.GTIN_13:
        result.company_prefix = cleaned[:7]
    elif gtin_type == GTINType.GTIN_14:
        result.company_prefix = cleaned[1:8]  # skip indicator digit
    elif gtin_type == GTINType.GTIN_8:
        result.company_prefix = cleaned[:4]

    return result


# =============================================================================
# Pasted input
# =============================================================================

_ENTRY_SEPARATORS = re.compile(r"[\r\n\t,;]+")


def split_gtin_entries(entries: list[str]) -> list[str]:
    """
    Split pasted text into one string per GTIN.

    Line breaks, tabs, commas, and semicolons always separate GTINs.
    Spaces are ambiguous: a barcode number as printed puts spaces between
    groups of six digits or fewer (0 36000 29145 2). So a piece is split
    on spaces only when one of its parts has seven or more digits.
    Otherwise it stays one entry, and validate_single_gtin removes the
    spaces. Blank pieces are dropped.
    """
    out: list[str] = []
    for entry in entries:
        for piece in _ENTRY_SEPARATORS.split(entry):
            parts = piece.split()
            if not parts:
                continue
            if len(parts) > 1 and any(
                sum(ch.isdigit() for ch in part) >= 7 for part in parts
            ):
                out.extend(parts)
            else:
                out.append(piece.strip())
    return out


# =============================================================================
# Batch validation
# =============================================================================

def validate_batch(gtins: list[str]) -> BatchResult:
    """
    Validate a batch of GTINs and return comprehensive results.

    Performs single-GTIN validation, then adds batch-level checks:
    duplicate detection, company prefix consistency, hierarchy analysis,
    missing case GTINs, retailer checklists, scoring, and cost estimates.

    Args:
        gtins: List of raw GTIN strings.

    Returns:
        Dict with keys: results, summary, duplicates, hierarchy,
        retailer_checklists, score, cost_estimate.
    """
    results = [
        validate_single_gtin(gtin, row_number=i + 1)
        for i, gtin in enumerate(gtins)
    ]

    # --- Duplicate detection ---
    cleaned_list = [r.cleaned for r in results if r.cleaned]
    counts = Counter(cleaned_list)
    duplicates = {k: v for k, v in counts.items() if v > 1}

    for result in results:
        if result.cleaned in duplicates:
            other_rows = [
                r.row_number for r in results
                if r.cleaned == result.cleaned and r.row_number != result.row_number
            ]
            result.issues.append(Issue(
                severity=Severity.WARNING,
                code="DUPLICATE",
                message=(
                    f"This GTIN appears {duplicates[result.cleaned]} times "
                    f"in your file (also on row(s) {', '.join(str(r) for r in other_rows)})."
                ),
                recommendation=(
                    "Each unique product configuration should have its own GTIN. "
                    "Duplicates usually mean the same GTIN was assigned to different "
                    "products, or the same product appears multiple times."
                ),
                retailer_impact=(
                    "Walmart and 1WorldSync will reject duplicate GTINs for different items. "
                    "If these are the same item listed twice, deduplicate your data."
                ),
            ))

    # --- Company prefix consistency ---
    prefixes = [r.company_prefix for r in results if r.company_prefix]
    prefix_counts = Counter(prefixes)
    if len(prefix_counts) > 1:
        dominant_prefix, dominant_count = prefix_counts.most_common(1)[0]
        for result in results:
            if result.company_prefix and result.company_prefix != dominant_prefix:
                result.issues.append(Issue(
                    severity=Severity.WARNING,
                    code="PREFIX_MISMATCH",
                    message=(
                        f"This GTIN's company prefix ({result.company_prefix}) differs from "
                        f"the most common prefix in your file ({dominant_prefix}, used by "
                        f"{dominant_count} of {len(prefixes)} GTINs)."
                    ),
                    recommendation=(
                        "This could mean: (1) you acquired this product from another company, "
                        "(2) you use multiple GS1 company prefixes, or (3) this GTIN was "
                        "entered incorrectly. Verify it matches your GS1 registration."
                    ),
                    retailer_impact=(
                        "Walmart's Verified by GS1 initiative cross-references GTIN ownership. "
                        "A prefix that doesn't match your company may flag your submission."
                    ),
                ))

    # --- Hierarchy analysis ---
    hierarchy = analyze_hierarchy(results)

    # --- Flag UPC-A items without a corresponding case GTIN-14 ---
    matched_unit_gtins = {p["unit_gtin"] for p in hierarchy["matched_pairs"]}
    for result in results:
        if (result.gtin_type == GTINType.GTIN_12
                and result.cleaned not in matched_unit_gtins):
            result.issues.append(Issue(
                severity=Severity.INFO,
                code="NO_CASE_GTIN",
                message=(
                    "This UPC-A has no corresponding case-level GTIN-14 in your file. "
                    "If you ship this product to retailers in cases, you need a GTIN-14."
                ),
                recommendation=(
                    "Create a GTIN-14 for each packaging level (inner pack, case, pallet). "
                    "The GTIN-14 uses an indicator digit (1-8) + your company prefix + "
                    "item reference + check digit."
                ),
                retailer_impact=(
                    "Walmart Item 360 requires GTINs at every packaging level. "
                    "Costco and UNFI require case GTINs for warehouse receiving. "
                    "Without a case GTIN, your item cannot be set up for shipping."
                ),
            ))

    # --- Retailer checklists ---
    retailer_checklists = generate_retailer_checklists(results, hierarchy)

    # --- Scoring ---
    score = calculate_readiness_score(results, hierarchy)

    # --- Cost of inaction ---
    cost_estimate = estimate_cost_of_inaction(results)

    # --- Summary stats ---
    total = len(results)
    summary: BatchSummary = {
        "total_gtins": total,
        "valid": sum(1 for r in results if r.is_valid and not r.has_critical),
        "critical_issues": sum(1 for r in results if r.has_critical),
        "warnings": sum(1 for r in results if r.has_warning and not r.has_critical),
        # Clean = no critical or warning issues. INFO-level advisories (e.g.
        # UPC_NOT_GTIN13 on every valid UPC-A) do not disqualify a row.
        "clean": sum(1 for r in results if not (r.has_critical or r.has_warning)),
        "duplicate_groups": len(duplicates),
        "unique_prefixes": len(prefix_counts),
    }

    return {
        "results": results,
        "summary": summary,
        "duplicates": duplicates,
        "hierarchy": hierarchy,
        "retailer_checklists": retailer_checklists,
        "score": score,
        "cost_estimate": cost_estimate,
    }


# =============================================================================
# Hierarchy analysis
# =============================================================================

def analyze_hierarchy(results: list[GTINResult]) -> dict:
    """
    Detect unit-to-case GTIN relationships via GTIN-14 indicator digits.

    A GTIN-14 with indicator 1-8 should share the same item reference
    as a corresponding GTIN-12 or GTIN-13 in the dataset.

    Returns:
        Dict with matched_pairs, orphan_cases, units_without_cases,
        has_hierarchy, and hierarchy_complete flags.
    """
    unit_gtins: dict[str, GTINResult] = {}
    case_gtins: list[GTINResult] = []

    for r in results:
        if r.gtin_type in (GTINType.GTIN_12, GTINType.GTIN_13):
            normalized = r.cleaned.zfill(13)
            unit_gtins[normalized[:-1]] = r  # store without check digit
        elif r.gtin_type == GTINType.GTIN_14 and r.indicator_digit and r.indicator_digit in "12345678":
            case_gtins.append(r)

    matched_pairs = []
    orphan_cases = []

    for case_r in case_gtins:
        inner = case_r.cleaned[1:-1]  # 12 digits: skip indicator + check
        if inner in unit_gtins:
            matched_pairs.append({
                "case_gtin": case_r.cleaned,
                "case_row": case_r.row_number,
                "unit_gtin": unit_gtins[inner].cleaned,
                "unit_row": unit_gtins[inner].row_number,
                "indicator": case_r.indicator_digit,
            })
        else:
            orphan_cases.append(case_r)
            case_r.issues.append(Issue(
                severity=Severity.WARNING,
                code="ORPHAN_CASE_GTIN",
                message=(
                    "This case-level GTIN-14 does not have a matching unit-level "
                    "GTIN (GTIN-12 or GTIN-13) in your file."
                ),
                recommendation=(
                    "Every case GTIN should correspond to a unit GTIN in your product master. "
                    "Either the unit GTIN is missing from your file, or this case GTIN's "
                    "item reference doesn't match any unit."
                ),
                retailer_impact=(
                    "Walmart requires a complete hierarchy (each → case → pallet). "
                    "A case GTIN without a matching unit will fail Item 360 setup."
                ),
            ))

    units_with_cases = {pair["unit_gtin"] for pair in matched_pairs}
    units_without_cases = [
        r for r in unit_gtins.values()
        if r.cleaned not in units_with_cases
    ]

    return {
        "matched_pairs": matched_pairs,
        "orphan_cases": orphan_cases,
        "units_without_cases": units_without_cases,
        "has_hierarchy": len(matched_pairs) > 0,
        "hierarchy_complete": len(orphan_cases) == 0 and len(units_without_cases) == 0,
    }


# =============================================================================
# Retailer-specific checklists
# =============================================================================

def generate_retailer_checklists(
    results: list[GTINResult],
    hierarchy: dict,
) -> dict:
    """
    Generate pass/fail checklists for each retailer profile.

    Each check includes a list of failing GTINs (row_number, raw_input)
    for drill-down in reports.
    """
    checklists = {}

    for retailer_name, profile in RETAILER_PROFILES.items():
        checks = []

        # Check 1: All GTINs valid
        invalid = [r for r in results if not r.is_valid]
        checks.append({
            "check": "All GTINs pass check digit validation",
            "passed": len(invalid) == 0,
            "detail": (
                f"{len(invalid)} GTIN(s) have invalid check digits"
                if invalid else "All check digits valid"
            ),
            "failing_gtins": [(r.row_number, r.raw_input) for r in invalid],
        })

        # Check 2: No duplicates
        dups = [r for r in results if any(i.code == "DUPLICATE" for i in r.issues)]
        dup_count = len({r.cleaned for r in dups})
        checks.append({
            "check": "No duplicate GTINs",
            "passed": dup_count == 0,
            "detail": (
                f"{dup_count} duplicate GTIN(s) found"
                if dup_count else "No duplicates"
            ),
            "failing_gtins": [(r.row_number, r.raw_input) for r in dups],
        })

        # Check 3: Accepted GTIN types
        wrong_type = [
            r for r in results
            if r.gtin_type not in profile["required_gtin_types"]
            and r.gtin_type != GTINType.UNKNOWN
        ]
        accepted = ", ".join(t.value for t in profile["required_gtin_types"])
        checks.append({
            "check": f"GTIN types accepted by {retailer_name}",
            "passed": len(wrong_type) == 0,
            "detail": (
                f"{len(wrong_type)} GTIN(s) use types not typically accepted"
                if wrong_type else f"All GTINs use accepted types ({accepted})"
            ),
            "failing_gtins": [(r.row_number, r.raw_input) for r in wrong_type],
        })

        # Check 4: Hierarchy (if required)
        if profile["requires_hierarchy"]:
            checks.append({
                "check": "Packaging hierarchy detected (unit → case relationships)",
                "passed": hierarchy["has_hierarchy"],
                "detail": (
                    f"{len(hierarchy['matched_pairs'])} unit-to-case pair(s) found"
                    if hierarchy["has_hierarchy"]
                    else "No packaging hierarchy detected in your data"
                ),
                "failing_gtins": [],
            })

        # Check 5: Case GTIN present (if required)
        if profile["requires_case_gtin"]:
            has_case = any(
                r.gtin_type == GTINType.GTIN_14 and r.indicator_digit and r.indicator_digit in "12345678"
                for r in results
            )
            checks.append({
                "check": "Case-level GTIN-14 present",
                "passed": has_case,
                "detail": (
                    "Case-level GTINs found"
                    if has_case
                    else "No case-level GTIN-14s found — you may need these for shipping/receiving"
                ),
                "failing_gtins": [],
            })

        # Check 6: Consistent company prefix
        prefix_failing = [
            r for r in results
            if any(i.code == "PREFIX_MISMATCH" for i in r.issues)
        ]
        checks.append({
            "check": "Consistent GS1 company prefix",
            "passed": len(prefix_failing) == 0,
            "detail": (
                "Multiple company prefixes detected — verify ownership"
                if prefix_failing
                else "All GTINs share a consistent company prefix"
            ),
            "failing_gtins": [(r.row_number, r.raw_input) for r in prefix_failing],
        })

        passed = sum(1 for c in checks if c["passed"])
        checklists[retailer_name] = {
            "profile": profile,
            "checks": checks,
            "passed": passed,
            "total": len(checks),
            "ready": passed == len(checks),
        }

    return checklists


# =============================================================================
# Readiness scoring
# =============================================================================

def calculate_readiness_score(
    results: list[GTINResult],
    hierarchy: dict,
) -> ScoreResult:
    """
    Calculate an overall submission readiness score (0–100).

    Scoring breakdown (rebased to 100 so clean data can earn Grade A):
        - 90 pts max: percentage of GTINs without critical issues. Clean,
          fully-valid data reaches 90 (Grade A) on validity alone — a file
          does not need case GTINs to be submission-ready.
        - -15 pts max: penalty for warning-only GTINs
        - +10 pts max: bonus for a complete packaging hierarchy (unit → case).
          Absent hierarchy is not penalized; hierarchy problems already
          surface as warnings, which the penalty above accounts for.
    """
    if not results:
        return {"score": 0, "grade": "N/A", "interpretation": "No GTINs to evaluate."}

    total = len(results)
    critical_count = sum(1 for r in results if r.has_critical)
    warning_count = sum(1 for r in results if r.has_warning and not r.has_critical)

    base = ((total - critical_count) / total) * 90
    warning_penalty = (warning_count / total) * 15

    hierarchy_bonus = 0
    if hierarchy["has_hierarchy"]:
        hierarchy_bonus = 10 if hierarchy["hierarchy_complete"] else 5

    score = max(0, min(100, round(base - warning_penalty + hierarchy_bonus)))

    grade_table = [
        (90, "A", "Your GTIN data is in strong shape. Minor cleanup may be needed."),
        (75, "B", "Most GTINs are valid but there are issues to fix before submission."),
        (60, "C", "Significant issues that will cause retailer rejections. Remediation needed."),
        (40, "D", "Major data quality problems. Expect widespread submission failures."),
        (0, "F", "GTIN data is not ready for retailer submission. Full audit and remediation required."),
    ]
    grade, interp = "F", grade_table[-1][2]
    for threshold, g, i in grade_table:
        if score >= threshold:
            grade, interp = g, i
            break

    return {"score": score, "grade": grade, "interpretation": interp}


# =============================================================================
# Cost-of-inaction estimates
# =============================================================================

# Default cost-of-inaction assumptions. These are directional planning
# figures for specialty food / CPG — NOT sourced facts. They are surfaced to
# the user as editable assumptions in the report (with the driver counts they
# multiply) rather than asserted as ground truth, so the dollar totals read as
# "your numbers, our arithmetic" instead of an unsupported claim.
COST_ASSUMPTIONS: dict[str, float] = {
    "chargeback_per_item_low": 200,       # $ per invalid item, low
    "chargeback_per_item_high": 500,      # $ per invalid item, high
    "delayed_launch_per_sku_low": 1000,   # $ per delayed SKU-month, low
    "delayed_launch_per_sku_high": 5000,  # $ per delayed SKU-month, high
    "delayed_sku_fraction": 0.25,         # share of critical items that stall a launch
    "rework_rate_per_hour": 50,           # $ per hour of manual rework
    "rework_hours_per_critical": 3,       # hours to fix one critical issue
    "rework_hours_per_warning": 1,        # hours to fix one warning
    "growth_multiplier_low": 3,           # cost scaling at 2x SKUs, low
    "growth_multiplier_high": 4,          # cost scaling at 2x SKUs, high
}


def estimate_cost_of_inaction(
    results: list[GTINResult],
    assumptions: Optional[dict[str, float]] = None,
) -> dict:
    """
    Estimate annual cost of unresolved GTIN issues.

    Every rate here is a planning ASSUMPTION, not a sourced figure. The
    assumptions used (and the driver counts they multiply) are returned
    alongside the estimate so the report can present them as editable inputs
    rather than presenting the dollar totals as established fact.

    Args:
        results: Validated GTIN results.
        assumptions: Optional overrides merged over COST_ASSUMPTIONS.
    """
    if not results:
        return {}

    a = {**COST_ASSUMPTIONS, **(assumptions or {})}

    critical_count = sum(1 for r in results if r.has_critical)
    warning_count = sum(1 for r in results if r.has_warning)
    total = len(results)

    chargeback_low = int(critical_count * a["chargeback_per_item_low"])
    chargeback_high = int(critical_count * a["chargeback_per_item_high"])

    delayed_skus = round(critical_count * a["delayed_sku_fraction"])
    delay_cost_low = int(delayed_skus * a["delayed_launch_per_sku_low"])
    delay_cost_high = int(delayed_skus * a["delayed_launch_per_sku_high"])

    rework_hours = int(
        (critical_count * a["rework_hours_per_critical"])
        + (warning_count * a["rework_hours_per_warning"])
    )
    rework_cost = int(rework_hours * a["rework_rate_per_hour"])

    growth_note = (
        f"Assumption: at 2x your current SKU count ({total * 2} SKUs) with "
        f"additional retailers, these costs are assumed to scale "
        f"{a['growth_multiplier_low']:g}-{a['growth_multiplier_high']:g}x. "
        f"Adjust the multiplier to your own retailer mix."
    )

    return {
        "chargeback_range": (chargeback_low, chargeback_high),
        "delayed_launch_range": (delay_cost_low, delay_cost_high),
        "rework_hours": rework_hours,
        "rework_cost": rework_cost,
        "annual_estimate_low": chargeback_low + delay_cost_low + rework_cost,
        "annual_estimate_high": chargeback_high + delay_cost_high + rework_cost,
        "growth_note": growth_note,
        "delayed_skus": delayed_skus,
        "assumptions": a,
        "drivers": {
            "critical_count": critical_count,
            "warning_count": warning_count,
            "total_gtins": total,
            "delayed_skus": delayed_skus,
            "rework_hours": rework_hours,
        },
    }


# =============================================================================
# Check digit corrections (before/after view)
# =============================================================================

def generate_before_after(results: list[GTINResult]) -> list[dict]:
    """
    Generate before/after pairs for GTINs with correctable check digits.

    Returns:
        List of dicts with row, before, after, and issue description.
    """
    return [
        {
            "row": r.row_number,
            "before": r.raw_input,
            "after": r.corrected_value or r.cleaned,
            "issue": next(
                (i.message for i in r.issues if i.code == "BAD_CHECK_DIGIT"),
                "See issues",
            ),
        }
        for r in results
        if r.corrected_value or any(i.code == "BAD_CHECK_DIGIT" for i in r.issues)
    ]


# =============================================================================
# Executive summary generator
# =============================================================================

def generate_executive_summary(validation_data: BatchResult) -> str:
    """
    Generate a plain-English executive summary suitable for copy/paste
    into an email or Slack message.
    """
    summary = validation_data["summary"]
    score = validation_data["score"]
    cost = validation_data["cost_estimate"]
    results = validation_data["results"]
    retailer_checklists = validation_data["retailer_checklists"]

    total = summary["total_gtins"]
    critical = summary["critical_issues"]
    clean = summary["clean"]
    dupes = summary["duplicate_groups"]

    lines = []

    # Opening
    if score["score"] >= 90:
        lines.append(
            f"Your product data is in strong shape. Of {total} GTINs analyzed, "
            f"{clean} passed all validation checks with no errors or warnings. "
            f"Your submission readiness score is {score['score']}/100 "
            f"(Grade: {score['grade']})."
        )
    elif score["score"] >= 75:
        lines.append(
            f"Of {total} GTINs analyzed, most are valid but there are issues to address. "
            f"Your submission readiness score is {score['score']}/100 (Grade: {score['grade']})."
        )
    else:
        lines.append(
            f"Of {total} GTINs analyzed, {critical} have critical issues that will block "
            f"retailer submission. Your submission readiness score is {score['score']}/100 "
            f"(Grade: {score['grade']})."
        )

    # Critical issues breakdown
    if critical > 0:
        code_names = {
            "BAD_CHECK_DIGIT": "check digit errors",
            "INVALID_LENGTH": "invalid length GTINs",
            "NON_NUMERIC": "GTINs with non-numeric characters",
            "ALL_ZEROS": "placeholder (all-zero) GTINs",
            "EMPTY": "empty/blank GTINs",
        }
        issue_codes: dict[str, int] = {}
        for r in results:
            for i in r.issues:
                if i.severity == Severity.CRITICAL:
                    issue_codes[i.code] = issue_codes.get(i.code, 0) + 1

        parts = [
            f"{count} {code_names.get(code, code)}"
            for code, count in issue_codes.items()
        ]
        lines.append(f"Critical issues include: {', '.join(parts)}.")

    # Duplicates
    if dupes > 0:
        lines.append(
            f"There are {dupes} duplicate GTIN(s) that will cause conflicts "
            f"in 1WorldSync and retailer item setup systems."
        )

    # Retailer readiness
    ready = [name for name, cl in retailer_checklists.items() if cl["ready"]]
    not_ready = [name for name, cl in retailer_checklists.items() if not cl["ready"]]
    if ready:
        lines.append(f"Your data is currently ready for submission to: {', '.join(ready)}.")
    if not_ready:
        lines.append(f"Your data is NOT ready for: {', '.join(not_ready)}.")

    # Cost
    if cost:
        lines.append(
            f"At your current SKU count, unresolved GTIN issues are estimated to cost "
            f"${cost['annual_estimate_low']:,}–${cost['annual_estimate_high']:,} annually "
            f"in chargebacks, delayed launches, and manual rework."
        )

    # Priority action
    if critical > 0:
        check_digit_errors = sum(
            1 for r in results
            if any(i.code == "BAD_CHECK_DIGIT" for i in r.issues)
        )
        if check_digit_errors > 0:
            lines.append(
                f"Priority fix: correct the {check_digit_errors} check digit error(s) first — "
                f"they're the fastest win with the highest impact on submission readiness."
            )

    return "\n\n".join(lines)


# =============================================================================
# Fix priority roadmap
# =============================================================================

# Effort/impact metadata for each issue type
_ISSUE_METADATA: dict[str, dict] = {
    "BAD_CHECK_DIGIT": {
        "effort": "Low",
        "effort_detail": "Fix the last digit — corrected values are provided in this report",
        "impact": "High",
        "impact_detail": "Blocks all retailer submissions",
        "time_estimate": "5 minutes per GTIN",
        "priority": 1,
    },
    "NON_NUMERIC": {
        "effort": "Low",
        "effort_detail": "Remove non-numeric characters from the GTIN",
        "impact": "High",
        "impact_detail": "Blocks all retailer submissions",
        "time_estimate": "2 minutes per GTIN",
        "priority": 2,
    },
    "INVALID_LENGTH": {
        "effort": "Medium",
        "effort_detail": "Investigate whether digits were truncated or added — may need original barcode",
        "impact": "High",
        "impact_detail": "Blocks all retailer submissions",
        "time_estimate": "10 minutes per GTIN",
        "priority": 3,
    },
    "ALL_ZEROS": {
        "effort": "Medium",
        "effort_detail": "Register a new GTIN with GS1 or retrieve the correct one",
        "impact": "High",
        "impact_detail": "Placeholder — item cannot be set up anywhere",
        "time_estimate": "15 min (if registered), days (if new registration needed)",
        "priority": 4,
    },
    "EMPTY": {
        "effort": "Medium",
        "effort_detail": "Determine if item needs a GTIN or should be removed from the file",
        "impact": "High",
        "impact_detail": "No retailer accepts items without GTINs",
        "time_estimate": "10 minutes per item",
        "priority": 5,
    },
    "DUPLICATE": {
        "effort": "Medium",
        "effort_detail": "Determine which item owns the GTIN and assign new GTINs to duplicates",
        "impact": "High",
        "impact_detail": "Causes item conflicts in 1WorldSync and retailer systems",
        "time_estimate": "15 minutes per duplicate group",
        "priority": 6,
    },
    "PREFIX_MISMATCH": {
        "effort": "Low",
        "effort_detail": "Verify whether the prefix is from an acquisition or a data entry error",
        "impact": "Medium",
        "impact_detail": "May flag submissions in Walmart's Verified by GS1 initiative",
        "time_estimate": "5 minutes per GTIN",
        "priority": 7,
    },
    "UPC_NOT_GTIN13": {
        "effort": "Low",
        "effort_detail": "Add a leading zero to convert UPC-A to GTIN-13 format",
        "impact": "Medium",
        "impact_detail": "Required for 1WorldSync and some international retailers",
        "time_estimate": "1 minute per GTIN (batch convertible)",
        "priority": 8,
    },
    "NO_CASE_GTIN": {
        "effort": "High",
        "effort_detail": "Create GTIN-14s for each packaging level — requires GS1 allocation",
        "impact": "High",
        "impact_detail": "Required for Walmart, Costco, UNFI warehouse receiving",
        "time_estimate": "1-2 weeks (GS1 registration + internal setup)",
        "priority": 9,
    },
    "ORPHAN_CASE_GTIN": {
        "effort": "Medium",
        "effort_detail": "Find or add the matching unit GTIN to your product master",
        "impact": "Medium",
        "impact_detail": "Incomplete hierarchy blocks Item 360 setup",
        "time_estimate": "15 minutes per orphan",
        "priority": 10,
    },
}

_DEFAULT_METADATA: dict = {
    "effort": "Unknown",
    "effort_detail": "",
    "impact": "Unknown",
    "impact_detail": "",
    "time_estimate": "Varies",
    "priority": 99,
}


def generate_fix_roadmap(
    results: list[GTINResult],
    hierarchy: dict,
) -> list[dict]:
    """
    Generate a prioritized fix roadmap ordered by impact × effort.

    Returns a list of action items sorted by priority (1 = fix first),
    each containing effort level, impact level, time estimate, and count.
    """
    issue_counts: dict[str, dict] = {}
    for r in results:
        for i in r.issues:
            if i.severity == Severity.INFO:
                continue  # skip info-level items
            if i.code not in issue_counts:
                issue_counts[i.code] = {
                    "count": 0,
                    "severity": i.severity,
                    "recommendation": i.recommendation,
                }
            issue_counts[i.code]["count"] += 1

    roadmap = []
    for code, data in issue_counts.items():
        meta = _ISSUE_METADATA.get(code, _DEFAULT_METADATA)
        roadmap.append({
            "priority": meta["priority"],
            "code": code,
            "action": data["recommendation"],
            "count": data["count"],
            "severity": data["severity"].value,
            "effort": meta["effort"],
            "effort_detail": meta["effort_detail"],
            "impact": meta["impact"],
            "impact_detail": meta["impact_detail"],
            "time_estimate": meta["time_estimate"],
        })

    roadmap.sort(key=lambda x: x["priority"])
    return roadmap


# =============================================================================
# GTIN-14 generation helper
# =============================================================================

_INDICATOR_LABELS: dict[int, str] = {
    1: "Case (most common)",
    2: "Inner pack",
    3: "Case (alternate)",
    4: "Case (alternate)",
    5: "Pallet",
    6: "Pallet (alternate)",
    7: "Reserved",
    8: "Reserved",
}


def generate_gtin14_suggestions(
    results: list[GTINResult],
    hierarchy: dict,
) -> list[dict]:
    """
    For unit GTINs missing case-level GTIN-14s, calculate what each
    GTIN-14 would be for indicator digits 1-8.

    Only suggests for valid unit GTINs without critical issues.
    """
    matched_unit_gtins = {pair["unit_gtin"] for pair in hierarchy["matched_pairs"]}
    suggestions = []

    for r in results:
        if r.gtin_type not in (GTINType.GTIN_12, GTINType.GTIN_13):
            continue
        if r.cleaned in matched_unit_gtins:
            continue
        if not r.is_valid or r.has_critical:
            continue

        normalized = r.cleaned.zfill(13)
        inner = normalized[:-1]  # 12 digits without check digit

        indicators = {}
        for ind in range(1, 9):
            payload = str(ind) + inner
            check = calculate_check_digit(payload)
            indicators[ind] = {
                "gtin14": payload + str(check),
                "label": _INDICATOR_LABELS[ind],
            }

        suggestions.append({
            "row": r.row_number,
            "unit_gtin": r.cleaned,
            "unit_type": r.gtin_type.value,
            "indicators": indicators,
        })

    return suggestions


# =============================================================================
# Data completeness check (CSV uploads with additional columns)
# =============================================================================

# Patterns to match common column names to standardized field names
_FIELD_PATTERNS: dict[str, list[str]] = {
    "product_name": ["product", "name", "item", "description", "title"],
    "brand": ["brand"],
    "weight": ["weight", "net_weight", "net weight", "gross_weight"],
    "height": ["height"],
    "width": ["width"],
    "depth": ["depth", "length"],
    "case_pack": ["case", "pack", "qty", "quantity", "count", "case_pack", "case pack"],
    "category": ["category", "class", "segment", "department"],
    "uom": ["uom", "unit of measure", "unit_of_measure"],
    "country_of_origin": ["country", "origin", "coo", "country_of_origin"],
    "ingredients": ["ingredient", "ingredients"],
    "allergens": ["allergen", "allergens"],
    "serving_size": ["serving", "serving_size", "serving size"],
    "calories": ["calorie", "calories", "kcal"],
    "shelf_life": ["shelf", "shelf_life", "shelf life", "expir"],
    "storage": ["storage", "temp", "temperature"],
    "image_url": ["image", "photo", "picture", "img", "url"],
}

# Fields that most retailers require for item setup
_IMPORTANT_FIELDS: list[str] = [
    "product_name", "brand", "weight", "height", "width", "depth",
    "case_pack", "category",
]

# Retailer-specific required fields
_RETAILER_REQUIRED_FIELDS: dict[str, list[str]] = {
    "Walmart": [
        "product_name", "brand", "weight", "height", "width", "depth",
        "case_pack", "category", "country_of_origin",
    ],
    "1WorldSync": [
        "product_name", "brand", "weight", "height", "width", "depth",
        "ingredients", "allergens", "serving_size", "calories",
        "country_of_origin", "image_url",
    ],
    "Costco": [
        "product_name", "brand", "weight", "case_pack",
        "country_of_origin", "shelf_life",
    ],
}


def check_data_completeness(df: pd.DataFrame) -> dict:
    """
    Analyze a product data DataFrame for field completeness.

    Checks which standard product attributes are present, how completely
    they're populated, and which retailer-required fields are missing.

    Args:
        df: DataFrame from the user's uploaded CSV.

    Returns:
        Dict with field_analysis, missing_important_fields,
        retailer_data_gaps, and overall_completeness score.
    """
    matched_columns: dict[str, str] = {}

    for field_name, patterns in _FIELD_PATTERNS.items():
        for col in df.columns:
            col_lower = col.lower().strip()
            if any(p in col_lower for p in patterns):
                if field_name not in matched_columns:
                    matched_columns[field_name] = col
                break

    total_rows = len(df)
    field_analysis: dict[str, dict] = {}

    for field_name, col in matched_columns.items():
        non_empty = int(df[col].apply(
            lambda x: bool(str(x).strip()) if pd.notna(x) else False
        ).sum())

        field_analysis[field_name] = {
            "column_name": col,
            "total_rows": total_rows,
            "populated": non_empty,
            "missing": total_rows - non_empty,
            "completeness_pct": round((non_empty / total_rows) * 100, 1) if total_rows > 0 else 0,
        }

    missing_fields = [f for f in _IMPORTANT_FIELDS if f not in matched_columns]

    # Retailer gap analysis
    retailer_gaps: dict[str, dict] = {}
    for retailer, required in _RETAILER_REQUIRED_FIELDS.items():
        present = [f for f in required if f in matched_columns]
        missing = [f for f in required if f not in matched_columns]
        partially_filled = [
            f for f in present
            if field_analysis[f]["completeness_pct"] < 100
        ]
        retailer_gaps[retailer] = {
            "required": len(required),
            "present": len(present),
            "missing_fields": missing,
            "incomplete_fields": partially_filled,
            "ready": len(missing) == 0 and len(partially_filled) == 0,
        }

    # Overall score includes missing important fields as 0%
    found_scores = sum(r["completeness_pct"] for r in field_analysis.values())
    denominator = len(field_analysis) + len(missing_fields)
    overall = round(found_scores / denominator, 1) if denominator > 0 else 0

    return {
        "field_analysis": field_analysis,
        "missing_important_fields": missing_fields,
        "retailer_data_gaps": retailer_gaps,
        "overall_completeness": overall,
    }
