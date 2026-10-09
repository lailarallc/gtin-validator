"""
Tests for the GTIN Validator core engine.

Run with: python -m pytest tests.py -v
"""

import pandas as pd

from gtin_core import (
    GTINType,
    Severity,
    calculate_check_digit,
    check_data_completeness,
    generate_before_after,
    generate_executive_summary,
    generate_fix_roadmap,
    generate_gtin14_suggestions,
    identify_gtin_type,
    split_gtin_entries,
    validate_batch,
    validate_single_gtin,
)

# =========================================================================
# Check digit calculation
# =========================================================================

class TestCheckDigit:
    """GS1 mod-10 check digit algorithm per General Specifications §7.9."""

    def test_gtin12_check_digit(self):
        # GS1 example: 61414100001 → check digit 2
        assert calculate_check_digit("61414100001") == 2

    def test_gtin13_check_digit(self):
        # EAN-13: 590123412345 → check digit 7
        assert calculate_check_digit("590123412345") == 7

    def test_gtin14_check_digit(self):
        # GTIN-14: 1061414100001 → check digit 9
        assert calculate_check_digit("1061414100001") == 9

    def test_gtin8_check_digit(self):
        # GTIN-8: 9638507 → check digit 4
        assert calculate_check_digit("9638507") == 4

    def test_all_zeros(self):
        assert calculate_check_digit("00000000000") == 0


# =========================================================================
# GTIN type identification
# =========================================================================

class TestGTINType:
    def test_gtin8(self):
        assert identify_gtin_type(8) == GTINType.GTIN_8

    def test_gtin12(self):
        assert identify_gtin_type(12) == GTINType.GTIN_12

    def test_gtin13(self):
        assert identify_gtin_type(13) == GTINType.GTIN_13

    def test_gtin14(self):
        assert identify_gtin_type(14) == GTINType.GTIN_14

    def test_unknown_lengths(self):
        for length in [0, 1, 5, 9, 10, 11, 15, 20]:
            assert identify_gtin_type(length) == GTINType.UNKNOWN


# =========================================================================
# Single GTIN validation
# =========================================================================

class TestSingleValidation:
    def test_valid_gtin12(self):
        result = validate_single_gtin("614141000012", row_number=1)
        assert result.gtin_type == GTINType.GTIN_12
        assert not result.has_critical
        assert not result.has_warning

    def test_empty_gtin(self):
        result = validate_single_gtin("", row_number=1)
        assert not result.is_valid
        assert result.has_critical
        assert result.issues[0].code == "EMPTY"

    def test_non_numeric(self):
        result = validate_single_gtin("6141410003A5", row_number=1)
        assert not result.is_valid
        assert result.issues[0].code == "NON_NUMERIC"

    def test_invalid_length(self):
        result = validate_single_gtin("61414100010", row_number=1)  # 11 digits
        assert not result.is_valid
        assert result.issues[0].code == "INVALID_LENGTH"

    def test_bad_check_digit(self):
        result = validate_single_gtin("614141000356", row_number=1)
        assert not result.is_valid
        assert any(i.code == "BAD_CHECK_DIGIT" for i in result.issues)
        assert result.corrected_value == "614141000357"

    def test_all_zeros(self):
        result = validate_single_gtin("000000000000", row_number=1)
        assert not result.is_valid
        assert any(i.code == "ALL_ZEROS" for i in result.issues)

    def test_gtin14_case_level(self):
        result = validate_single_gtin("10614141000019", row_number=1)
        assert result.gtin_type == GTINType.GTIN_14
        assert result.indicator_digit == "1"
        assert any(i.code == "CASE_LEVEL" for i in result.issues)

    def test_gtin14_indicator_nine(self):
        result = validate_single_gtin("90614141000016", row_number=1)
        assert any(i.code == "INDICATOR_NINE" for i in result.issues)

    def test_strips_whitespace_and_dashes(self):
        result = validate_single_gtin(" 614-141-000012 ", row_number=1)
        assert result.cleaned == "614141000012"
        assert not result.has_critical

    def test_upc_gtin13_info(self):
        result = validate_single_gtin("614141000012", row_number=1)
        upc_issue = next(i for i in result.issues if i.code == "UPC_NOT_GTIN13")
        assert upc_issue.severity == Severity.INFO

    def test_company_prefix_extracted_gtin12(self):
        # GTIN-12 prefix is sliced from the zero-padded (GTIN-13) form so it
        # aligns with the prefix embedded in a case-level GTIN-14.
        result = validate_single_gtin("614141000012", row_number=1)
        assert result.company_prefix == "0614141"

    def test_company_prefix_extracted_gtin14(self):
        result = validate_single_gtin("10614141000019", row_number=1)
        assert result.company_prefix == "0614141"

    def test_unit_and_derived_case_share_company_prefix(self):
        # A valid UPC-A and the GTIN-14 built from it (indicator digit +
        # zero-padded item reference + recomputed check digit) must yield the
        # same company prefix — and therefore no PREFIX_MISMATCH warning.
        unit = "614141000012"
        inner = unit.zfill(13)[:-1]  # 12 digits: zero-pad, drop check digit
        case = "1" + inner + str(calculate_check_digit("1" + inner))

        unit_result = validate_single_gtin(unit, row_number=1)
        case_result = validate_single_gtin(case, row_number=2)
        assert case_result.is_valid
        assert unit_result.company_prefix == case_result.company_prefix

        data = validate_batch([unit, case])
        for r in data["results"]:
            assert not any(i.code == "PREFIX_MISMATCH" for i in r.issues)
        assert data["summary"]["unique_prefixes"] == 1


# =========================================================================
# Batch validation
# =========================================================================

class TestBatchValidation:
    def test_duplicate_detection(self):
        data = validate_batch(["614141000012", "614141000012"])
        assert data["summary"]["duplicate_groups"] == 1
        for r in data["results"]:
            assert any(i.code == "DUPLICATE" for i in r.issues)

    def test_prefix_mismatch_detection(self):
        data = validate_batch([
            "614141000012",
            "614141000029",
            "732141000013",  # different prefix
        ])
        mismatched = [r for r in data["results"] if any(
            i.code == "PREFIX_MISMATCH" for i in r.issues
        )]
        assert len(mismatched) == 1
        assert mismatched[0].company_prefix == "0732141"

    def test_summary_counts(self):
        data = validate_batch([
            "614141000012",   # valid (with UPC warning)
            "61414100010",    # critical: invalid length
            "000000000000",   # critical: all zeros
        ])
        assert data["summary"]["total_gtins"] == 3
        assert data["summary"]["critical_issues"] == 2

    def test_score_returned(self):
        data = validate_batch(["614141000012"])
        assert "score" in data["score"]
        assert "grade" in data["score"]
        assert 0 <= data["score"]["score"] <= 100

    def test_cost_estimate_returned(self):
        data = validate_batch(["61414100010"])  # will have critical issue
        cost = data["cost_estimate"]
        assert cost["chargeback_range"][0] <= cost["chargeback_range"][1]
        assert cost["annual_estimate_low"] <= cost["annual_estimate_high"]

    def test_empty_batch(self):
        data = validate_batch([])
        assert data["summary"]["total_gtins"] == 0
        assert data["score"]["score"] == 0

    def test_valid_upc_batch_scores_high(self):
        data = validate_batch([
            "614141000012",
            "614141000029",
            "614141000036",
            "614141000043",
            "614141000050",
        ])
        assert data["score"]["score"] >= 70
        assert data["summary"]["critical_issues"] == 0


# =========================================================================
# Pasted input
# =========================================================================

class TestSplitGtinEntries:
    def test_one_per_line_unchanged(self):
        assert split_gtin_entries(["614141000012", "614141000029"]) == [
            "614141000012",
            "614141000029",
        ]

    def test_commas_semicolons_tabs_and_line_breaks(self):
        assert split_gtin_entries(
            ["614141000012, 614141000029;614141000036\t614141000043\n614141000050"]
        ) == [
            "614141000012",
            "614141000029",
            "614141000036",
            "614141000043",
            "614141000050",
        ]

    def test_spaces_between_gtins(self):
        assert split_gtin_entries(["614141000012 614141000019 12345"]) == [
            "614141000012",
            "614141000019",
            "12345",
        ]

    def test_printed_spaces_stay_one_gtin(self):
        entries = split_gtin_entries(["6 14141 00001 2"])
        assert entries == ["6 14141 00001 2"]
        data = validate_batch(entries)
        assert data["summary"]["total_gtins"] == 1
        assert data["summary"]["critical_issues"] == 0

    def test_blank_pieces_dropped(self):
        assert split_gtin_entries(["", "   ", "614141000012,,", " ;\t"]) == [
            "614141000012"
        ]


# =========================================================================
# Hierarchy analysis
# =========================================================================

class TestHierarchy:
    def test_matched_pair(self):
        data = validate_batch([
            "614141000012",    # unit GTIN-12
            "10614141000019",  # case GTIN-14 (indicator 1)
        ])
        assert len(data["hierarchy"]["matched_pairs"]) == 1
        assert data["hierarchy"]["has_hierarchy"] is True

    def test_orphan_case(self):
        data = validate_batch([
            "10999999999993",  # case GTIN-14 with no matching unit
        ])
        assert len(data["hierarchy"]["orphan_cases"]) == 1

    def test_no_hierarchy(self):
        data = validate_batch(["614141000012"])
        assert data["hierarchy"]["has_hierarchy"] is False


# =========================================================================
# Before/after corrections
# =========================================================================

class TestBeforeAfter:
    def test_correction_generated(self):
        data = validate_batch(["614141000356"])  # bad check digit
        pairs = generate_before_after(data["results"])
        assert len(pairs) == 1
        assert pairs[0]["after"] == "614141000357"

    def test_no_corrections_when_valid(self):
        data = validate_batch(["614141000012"])
        pairs = generate_before_after(data["results"])
        assert len(pairs) == 0


# =========================================================================
# Executive summary
# =========================================================================

class TestExecutiveSummary:
    def test_returns_string(self):
        data = validate_batch(["614141000012", "61414100010"])
        summary = generate_executive_summary(data)
        assert isinstance(summary, str)
        assert len(summary) > 50

    def test_mentions_score(self):
        data = validate_batch(["614141000012"])
        summary = generate_executive_summary(data)
        assert "/100" in summary


# =========================================================================
# Fix roadmap
# =========================================================================

class TestFixRoadmap:
    def test_roadmap_sorted_by_priority(self):
        data = validate_batch([
            "614141000012",   # UPC warning + no case GTIN
            "61414100010",    # invalid length (critical)
            "614141000356",   # bad check digit (critical)
        ])
        roadmap = generate_fix_roadmap(data["results"], data["hierarchy"])
        priorities = [item["priority"] for item in roadmap]
        assert priorities == sorted(priorities)

    def test_info_items_excluded(self):
        data = validate_batch(["10614141000019"])  # GTIN-14, info only
        roadmap = generate_fix_roadmap(data["results"], data["hierarchy"])
        # Should not include CASE_LEVEL info item
        codes = [item["code"] for item in roadmap]
        assert "CASE_LEVEL" not in codes


# =========================================================================
# GTIN-14 suggestions
# =========================================================================

class TestGTIN14Suggestions:
    def test_suggestion_generated(self):
        data = validate_batch(["614141000012"])
        suggestions = generate_gtin14_suggestions(
            data["results"], data["hierarchy"]
        )
        assert len(suggestions) == 1
        assert len(suggestions[0]["indicators"]) == 8

    def test_check_digit_correct_on_suggestions(self):
        data = validate_batch(["614141000012"])
        suggestions = generate_gtin14_suggestions(
            data["results"], data["hierarchy"]
        )
        for ind, info in suggestions[0]["indicators"].items():
            gtin14 = info["gtin14"]
            assert len(gtin14) == 14
            # Verify check digit
            payload = gtin14[:-1]
            expected = calculate_check_digit(payload)
            assert int(gtin14[-1]) == expected

    def test_no_suggestion_for_invalid_gtin(self):
        data = validate_batch(["61414100010"])  # invalid length
        suggestions = generate_gtin14_suggestions(
            data["results"], data["hierarchy"]
        )
        assert len(suggestions) == 0


# =========================================================================
# Edge cases
# =========================================================================

class TestEdgeCases:
    def test_dashes_only_cleans_to_empty(self):
        result = validate_single_gtin("---", row_number=1)
        assert not result.is_valid
        assert result.has_critical
        assert result.issues[0].code == "EMPTY"

    def test_spaces_only_cleans_to_empty(self):
        result = validate_single_gtin("   ", row_number=1)
        assert not result.is_valid
        assert result.issues[0].code == "EMPTY"

    def test_single_gtin_batch(self):
        data = validate_batch(["614141000012"])
        assert data["summary"]["total_gtins"] == 1
        assert 0 <= data["score"]["score"] <= 100
        assert data["cost_estimate"] is not None

    def test_all_duplicates_batch(self):
        data = validate_batch(["614141000012"] * 5)
        assert data["summary"]["total_gtins"] == 5
        assert data["summary"]["duplicate_groups"] >= 1
        for r in data["results"]:
            assert any(i.code == "DUPLICATE" for i in r.issues)


# =========================================================================
# Retailer checklists (via validate_batch)
# =========================================================================

class TestRetailerChecklists:
    def test_checklists_returned_for_all_retailers(self):
        data = validate_batch(["614141000012"])
        checklists = data["retailer_checklists"]
        assert "Walmart" in checklists
        assert "Costco" in checklists
        assert "UNFI" in checklists

    def test_checklist_structure(self):
        data = validate_batch(["614141000012"])
        for name, checklist in data["retailer_checklists"].items():
            assert "ready" in checklist
            assert "checks" in checklist
            assert "passed" in checklist
            assert "total" in checklist
            assert isinstance(checklist["checks"], list)

    def test_clean_data_passes_basic_checks(self):
        data = validate_batch(["0614141000012"])  # valid GTIN-13
        checklists = data["retailer_checklists"]
        for name, checklist in checklists.items():
            assert checklist["passed"] > 0


# =========================================================================
# Data completeness
# =========================================================================

class TestDataCompleteness:
    def test_basic_completeness(self):
        df = pd.DataFrame({
            "GTIN": ["614141000012"],
            "Product Name": ["Test Product"],
            "Brand": ["Test Brand"],
        })
        result = check_data_completeness(df)
        assert "field_analysis" in result
        assert "missing_important_fields" in result
        assert "retailer_data_gaps" in result
        assert "overall_completeness" in result

    def test_missing_fields_detected(self):
        df = pd.DataFrame({"GTIN": ["614141000012"]})
        result = check_data_completeness(df)
        assert len(result["missing_important_fields"]) > 0

    def test_empty_dataframe(self):
        df = pd.DataFrame({"GTIN": pd.Series(dtype=str)})
        result = check_data_completeness(df)
        assert result["overall_completeness"] == 0


# =========================================================================
# CSV report
# =========================================================================

class TestCSVReport:
    def _sample_data(self):
        return validate_batch(["614141000012", "invalid", "614141000029"])

    def test_csv_returns_string(self):
        from csv_report import generate_csv_report
        csv_out = generate_csv_report(self._sample_data())
        assert isinstance(csv_out, str)
        assert len(csv_out) > 0

    def test_csv_header_row(self):
        from csv_report import generate_csv_report
        csv_out = generate_csv_report(self._sample_data())
        header = csv_out.splitlines()[0]
        assert "GTIN (Original)" in header
        assert "Valid" in header
        assert "Issues" in header

    def test_csv_row_count(self):
        from csv_report import generate_csv_report
        csv_out = generate_csv_report(self._sample_data())
        lines = [line for line in csv_out.splitlines() if line.strip()]
        assert len(lines) == 4  # header + 3 GTINs

    def test_csv_sanitizes_formulas(self):
        from csv_report import _sanitize_cell
        assert _sanitize_cell("=SUM(A1)") == "'=SUM(A1)"
        assert _sanitize_cell("+cmd") == "'+cmd"
        assert _sanitize_cell("normal") == "normal"
        assert _sanitize_cell("") == ""


# =========================================================================
# Corrected CSV
# =========================================================================

class TestCorrectedCSV:
    def test_corrected_csv_fixes_check_digit(self):
        from csv_report import generate_corrected_csv
        data = validate_batch(["614141000011"])  # bad check digit (should be 2)
        csv_out = generate_corrected_csv(data)
        lines = csv_out.splitlines()
        assert "614141000012" in lines[1]
        assert "Fixed" in lines[1]

    def test_corrected_csv_valid_gtin_unchanged(self):
        from csv_report import generate_corrected_csv
        data = validate_batch(["614141000012"])
        csv_out = generate_corrected_csv(data)
        lines = csv_out.splitlines()
        assert "OK" in lines[1]
        assert "614141000012" in lines[1]

    def test_corrected_csv_unfixable_flagged(self):
        from csv_report import generate_corrected_csv
        data = validate_batch(["abc123"])
        csv_out = generate_corrected_csv(data)
        lines = csv_out.splitlines()
        assert "Needs manual fix" in lines[1]

    def test_corrected_csv_cleaned_whitespace(self):
        from csv_report import generate_corrected_csv
        data = validate_batch(["614141 000012"])
        csv_out = generate_corrected_csv(data)
        lines = csv_out.splitlines()
        assert "Cleaned" in lines[1]

    def test_corrected_csv_row_count(self):
        from csv_report import generate_corrected_csv
        data = validate_batch(["614141000012", "invalid", "614141000029"])
        csv_out = generate_corrected_csv(data)
        lines = [line for line in csv_out.splitlines() if line.strip()]
        assert len(lines) == 4  # header + 3


# =========================================================================
# PDF report
# =========================================================================

class TestPDFReport:
    def _sample_data(self):
        return validate_batch(["614141000012", "invalid", "614141000029"])

    def test_pdf_returns_bytes(self):
        from pdf_report import generate_pdf_report
        buf = generate_pdf_report(self._sample_data())
        data = buf.getvalue()
        assert isinstance(data, bytes)
        assert data[:5] == b"%PDF-"

    def test_pdf_with_company_name(self):
        from pdf_report import generate_pdf_report
        buf = generate_pdf_report(self._sample_data(), company_name="Cedar Hollow Provisions")
        data = buf.getvalue()
        assert len(data) > 0
        assert data[:5] == b"%PDF-"

    def test_pdf_empty_batch(self):
        from pdf_report import generate_pdf_report
        data = validate_batch([])
        buf = generate_pdf_report(data)
        assert buf.getvalue()[:5] == b"%PDF-"
