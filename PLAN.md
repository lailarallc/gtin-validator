# GTIN Validator — Free App Limit Plan

**Source:** Free app limit build plan (2026-10-07)
**Branch:** `free-app-limit` — PR only, do not merge. Merge on launch day (Fri 2026-10-16) once the kit is on Payhip and lailarallc.com/kits/gtin-validator is live.
**Status:** In progress

**Goal:** Sample data keeps the full report and downloads. Own data (upload or paste) shows only score, grade, and issue counts, with no row-level detail and no downloads, and points to the GTIN Validator Kit. The server enforces the limit.

**Constraints:** Don't touch `gtin_core.py`; `test_golden.py` passes unchanged. One commit per step. No raw exceptions in API errors.

- [x] 0. Set up — branch `free-app-limit`, plan in PLAN.md
- [x] 1. Limit the server — `POST /api/sample/validate` (full response + token); own-data endpoints return `{ summary, score }` only, no cache, no token; tests
- [x] 2. Change the results screens — `SummaryResponse` in api.ts, `runSample()`, own-data CTA, sample CTA, remove "free read" lines and `/services` links
- [x] 3. Update the page copy — index.html meta/og description, HeroSection subtitle + "What you'll need" card
- [x] 4. Fix the sample PDF — ● → •, ✓/✗ → PASS/FAIL, new closing paragraph, no U+25CF/U+2713/U+2717 in extracted text
- [ ] 5. Wrap up — DECISIONS.md entry, HANDOFF.md, open PR (don't merge)

---

# Prior plan: Prospect-Readiness (complete)


**Source:** Full project audit v2 (2026-05-16)
**Tier:** Medium
**Status:** Complete — all 7 goals shipped (2026-05-16, PR #12)
**Prior plan:** Complete — all 10 goals from v1 audit shipped (2026-05-15)

---

## Decomposition: All Prospect Demo Fixes

All 7 goals are independent — no dependencies between them. Grouped into two batches by file location for efficient execution.

### Batch A — Frontend fixes (Goals 1, 2, 4, 7)

- [x] 1.1: Fix page title in `frontend/index.html` — change `<title>frontend</title>` to `<title>GTIN Product Data Validator</title>`
    - Depends on: none
    - Done when: browser tab shows "GTIN Product Data Validator"
- [x] 1.2: Add meta description + OG tags to `frontend/index.html`
    - Depends on: 1.1
    - Done when: `<meta name="description">`, `og:title`, `og:description`, `og:type` all present
- [x] 2.1: Add error state to `DownloadButton` in `frontend/src/components/DownloadReports.tsx` — catch errors in onClick, display message below button
    - Depends on: none
    - Done when: simulating a failed download (e.g. expired token) shows an error message instead of silent failure
- [x] 4.1: Add empty-paste guard in `frontend/src/components/InputSection.tsx` — show inline message when user clicks Validate with empty textarea
    - Depends on: none
    - Done when: clicking "Validate GTINs" with empty text shows "Paste some GTINs first" (or similar); message clears on typing
- [x] 7.1: Add AbortController with 30s timeout to `request()` in `frontend/src/api.ts`
    - Depends on: none
    - Done when: `request()` aborts after 30s and throws an error with a user-friendly message
- [x] 7.2: Add timeout to `downloadBlob()` in `frontend/src/api.ts`
    - Depends on: none
    - Done when: download calls also abort after 30s with friendly message
- [x] A.verify: Build frontend — `cd frontend && npm run build`
    - Depends on: 1.1, 1.2, 2.1, 4.1, 7.1, 7.2
    - Done when: build succeeds with no TypeScript errors

### Batch B — Backend fixes (Goals 3, 5, 6)

- [x] 3.1: Sanitize error message in `backend/routes/validate.py:101-102` — replace `f"Error reading file: {exc}"` with generic message, log the real error
    - Depends on: none
    - Done when: uploading a malformed file returns "Could not read file. Please check the format." (not Python internals)
- [x] 5.1: Add filename sanitization helper in `backend/routes/reports.py` — strip everything except alphanumeric, hyphens, underscores from company_name
    - Depends on: none
    - Done when: `company_name="Café & Co."` produces filename `Caf_Co_report.csv`, not `Café_&_Co._report.csv`
- [x] 6.1: Change `async def validate_upload` to `def validate_upload` in `backend/routes/validate.py` — replace `await file.read()` with `file.file.read()`
    - Depends on: none
    - Done when: endpoint still works, `pytest tests_api.py -v` passes
- [x] B.verify: Run all backend tests — `pytest tests.py tests_api.py -v`
    - Depends on: 3.1, 5.1, 6.1
    - Done when: all 83 tests pass

### Final verification
- [x] F.1: Run full CI checks locally — tests, lint, typecheck, frontend build
    - Depends on: A.verify, B.verify
    - Done when: all pass clean

---

## Prospect Demo Fixes (from Audit v2, Phase 4)

### Goal 1: Fix page title + add meta/OG tags
**Source:** Audit Phase 4, Move #2
**Category:** Foundational
**Priority:** 1

**Objective:** Replace Vite default `<title>frontend</title>` with proper title, add meta description and OpenGraph tags for professional link sharing.

**Success Criteria:**
- Browser tab says "GTIN Product Data Validator"
- Sharing URL in Slack/email shows title, description, and (optionally) preview image
- `frontend/index.html` has `<meta name="description">`, `og:title`, `og:description`

### Goal 2: Fix download error handling
**Source:** Audit Phase 4, Move #1
**Category:** Double down (protects unique differentiator)
**Priority:** 2

**Objective:** DownloadButton shows an error message when download fails instead of silently swallowing it.

**Success Criteria:**
- Failed download shows user-friendly error (e.g., "Download failed. Try again.")
- Loading spinner stops on error (already works)
- Error clears when user retries

**Context:** Branded PDF is a unique differentiator — no competitor offers it. Silent failures break this during a demo.

### Goal 3: Sanitize error messages
**Source:** Audit Phase 4, Move #3
**Category:** Foundational
**Priority:** 3

**Objective:** Replace raw exception messages in API responses with user-friendly text. Log full errors server-side.

**Success Criteria:**
- `backend/routes/validate.py:101-102` no longer exposes `{exc}` to client
- Error message says something like "Could not read file. Please check the format."
- Full exception still logged for debugging

### Goal 4: Add empty-paste feedback
**Source:** Audit Phase 4, Move #4
**Category:** Foundational
**Priority:** 4

**Objective:** Show feedback when user clicks "Validate GTINs" with empty textarea.

**Success Criteria:**
- Empty paste + click shows a message like "Paste some GTINs first"
- Message clears when user starts typing

### Goal 5: Sanitize company_name in filenames
**Source:** Audit Phase 4, Move #6
**Category:** Foundational
**Priority:** 5

**Objective:** Strip special characters from company_name before using it in Content-Disposition filename.

**Success Criteria:**
- Only alphanumeric, hyphens, underscores in filenames
- company_name with special chars produces clean filename
- Empty company_name still falls back to "gtin_report"

### Goal 6: Fix async/sync in validate_upload
**Source:** Audit Phase 4, Move #7
**Category:** Foundational
**Priority:** 6

**Objective:** Change `async def validate_upload` to `def validate_upload` so FastAPI runs it in a threadpool instead of blocking the event loop.

**Success Criteria:**
- Endpoint works identically (same inputs/outputs)
- `file.read()` call updated from `await file.read()` to sync equivalent
- All API tests pass

### Goal 7: Add API timeout with friendly message
**Source:** Audit Phase 4, Move #8
**Category:** Foundational
**Priority:** 7

**Objective:** Add AbortController with 30-second timeout to frontend fetch calls. Show friendly message instead of infinite spinner.

**Success Criteria:**
- API calls abort after 30 seconds
- User sees "Request timed out — the server may be starting up. Try again in a moment." instead of infinite spinner
- Normal requests unaffected

---

## Decomposition: All Goals by Sprint

### Sprint 1 — Fix what's broken (~1-2 hours)

**Goal 1: Fix Readiness Score Accuracy**
- [x] 1.1: Change `UPC_NOT_GTIN13` severity from `Severity.WARNING` to `Severity.INFO` in `gtin_core.py:349`
    - Depends on: none
    - Done when: `validate_single_gtin("614141000012", 1)` produces an INFO issue, not WARNING
- [x] 1.2: Update `test_upc_gtin13_warning` to assert INFO severity instead of WARNING
    - Depends on: 1.1
    - Done when: `pytest tests.py::TestSingleValidation::test_upc_gtin13_warning -v` passes
- [x] 1.3: Add test: a batch of 5 valid GTIN-12s (no other issues) scores 70+
    - Depends on: 1.1
    - Done when: new test passes, confirming valid UPC-only datasets no longer penalized
- [x] 1.4: Run full test suite, verify no regressions
    - Depends on: 1.1, 1.2, 1.3
    - Done when: `pytest tests.py -v` — all tests pass

**Goal 2: Fix Dead Code and Add Input Guard**
- [x] 2.1: Remove the redundant `report_title` reassignment at `pdf_report.py:124-125`
    - Depends on: none
    - Done when: the `if company_name:` block either sets a different title or is removed
- [x] 2.2: Add paste input size cap (10,000 lines) with warning in `app.py` near line 188
    - Depends on: none
    - Done when: pasting >10K lines shows a warning and truncates/refuses, pasting <10K works normally
- [x] 2.3: Run full test suite
    - Depends on: 2.1, 2.2
    - Done when: `pytest tests.py -v` — all tests pass

**Goal 3: Add Project CLAUDE.md**
- [x] 3.1: Write `CLAUDE.md` in project root covering stack, file roles, test commands, deployment, current focus
    - Depends on: none
    - Done when: file exists and a fresh Claude Code session would have project context without reading every file

---

### Sprint 2 — Engineering foundation (~2-3 hours)

**Goal 4: Evaluate and Merge Security Branch**
- [x] 4.1: Review `origin/claude/security-code-audit-6k0Fg` diff against main — list each commit with keep/skip/adapt verdict
    - Depends on: none
    - Done when: written verdict for each of the 5 commits on the branch
- [x] 4.2: Cherry-pick or adapt viable commits (CI workflow, tests, robustness fixes)
    - Depends on: 4.1
    - Done when: selected work applied to current branch without conflicts
- [x] 4.3: Run full test suite after cherry-picks
    - Depends on: 4.2
    - Done when: `pytest tests.py -v` — all tests pass (including any new tests from the branch)

**Goal 5: Add CI/CD with Green README Badge**
- [x] 5.1: Create `.github/workflows/ci.yml` — pytest on push to main + PRs, Python 3.10/3.12 matrix
    - Depends on: 4.2 (may reuse CI from security branch)
    - Done when: workflow file exists with correct syntax (`actionlint` or manual review)
- [x] 5.2: Add green badge markdown to top of `README.md`
    - Depends on: 5.1
    - Done when: badge markup in README references the correct workflow
- [x] 5.3: Push and verify CI passes on GitHub
    - Depends on: 5.1, 5.2
    - Done when: GitHub Actions shows green check on the pushed commit

**Goal 6: Add Linting and Type Checking Config**
- [x] 6.1: Add ruff config to `pyproject.toml`, run `ruff check .`, fix or suppress issues
    - Depends on: none
    - Done when: `ruff check .` exits clean
- [x] 6.2: Add mypy config to `pyproject.toml`, run `mypy`, fix or annotate critical issues
    - Depends on: none
    - Done when: `mypy` exits with 0 errors (warnings acceptable)
- [x] 6.3: Add ruff + mypy steps to CI workflow
    - Depends on: 5.1, 6.1, 6.2
    - Done when: CI workflow includes lint and type-check steps

---

### Sprint 3 — Strengthen differentiators (~3-4 hours)

**Goal 7: Surface Company Name in Main Flow**
- [x] 7.1: Move company name `text_input` from sidebar to the main flow (above or alongside the action buttons)
    - Depends on: none
    - Done when: company name input visible on page load without opening sidebar
- [x] 7.2: Verify PDF report receives the company name and renders it correctly
    - Depends on: 7.1
    - Done when: downloading a PDF after entering a company name shows the name in the report
- [x] 7.3: Clean up sidebar — remove the company name input, keep retailer filter and "How it works"
    - Depends on: 7.1
    - Done when: sidebar no longer has a duplicate company name field

**Goal 8: Add Report Generator Tests**
- [x] 8.1: Add CSV report smoke tests — call `generate_csv_report` with valid data, verify returns non-empty string with expected headers
    - Depends on: none
    - Done when: new tests pass in `pytest tests.py -v`
- [x] 8.2: Add PDF report smoke tests — call `generate_pdf_report` with valid data, verify returns non-empty BytesIO
    - Depends on: none
    - Done when: new tests pass
- [x] 8.3: Add edge case tests — empty results, all-critical dataset, no-issues dataset, missing company name
    - Depends on: 8.1, 8.2
    - Done when: all edge case tests pass without exceptions

**Goal 9: TypedDict for validate_batch Return**
- [x] 9.1: Define `ValidationData` TypedDict (and sub-types for summary, score, cost) in `gtin_core.py`
    - Depends on: none
    - Done when: types defined and `validate_batch` return type annotated
- [x] 9.2: Update `validate_batch` to construct and return the typed structure
    - Depends on: 9.1
    - Done when: `validate_batch` returns `ValidationData`, all existing tests pass
- [x] 9.3: Update type annotations in consumers — `app.py`, `pdf_report.py`, `csv_report.py`
    - Depends on: 9.1, 9.2
    - Done when: function signatures reference the new types
- [x] 9.4: Run mypy, confirm type safety across the codebase
    - Depends on: 6.2, 9.3
    - Done when: `mypy` shows no new errors related to validation data access

**Goal 10: Deduplicate PDF Report Rendering**
- [x] 10.1: Consolidate `render_group_with_continuation` and `render_multi_issue_group` into a single function with optional `recommendation_text` parameter
    - Depends on: 8.2 (report tests provide safety net)
    - Done when: one function, ~80 lines removed, all tests pass
- [x] 10.2: Verify PDF output — generate PDF with sample data, confirm structure is unchanged
    - Depends on: 10.1
    - Done when: PDF has same sections, groupings, and page breaks as before

---

## Goal 1: Fix Readiness Score Accuracy
**Source:** Audit Phase 4, Move #1
**Category:** Double down
**Priority:** 1 — highest leverage finding

### Objective
Downgrade `UPC_NOT_GTIN13` from WARNING to INFO severity so valid UPC-A datasets score accurately for US retailers.

### Success Criteria
- A dataset of valid GTIN-12s with no other issues scores 70+ (not 55)
- Existing tests updated to reflect new severity
- Readiness score still penalizes actual problems (bad check digits, duplicates, etc.)

### Context
Phase 2 finding #1: every valid UPC-A triggers a WARNING, which inflates the warning count and penalizes the readiness score by up to 15 points. A dataset of perfectly valid US barcodes gets a C. This undermines the tool's core value prop for the primary audience (US specialty food brands). File: `gtin_core.py:349-368`.

---

## Goal 2: Fix Dead Code and Add Input Guard
**Source:** Audit Phase 4, Moves #9, #11
**Category:** Foundational
**Priority:** 2 — trivial effort, removes rough edges

### Objective
Fix the dead code in pdf_report.py:125 and add a paste input size cap.

### Success Criteria
- pdf_report.py no longer has the redundant string reassignment
- Paste input capped at 10,000 lines with a user-friendly warning
- No regressions in existing tests

### Context
Phase 2 findings #9 and #11. The dead code is a leftover from when the PDF title was supposed to include company name. The input guard prevents session crashes from oversized paste input.

---

## Goal 3: Add Project CLAUDE.md
**Source:** Audit Phase 4, Move #6
**Category:** Foundational
**Priority:** 3 — quick win for session efficiency

### Objective
Create a project-level CLAUDE.md with stack, conventions, key files, and current focus.

### Success Criteria
- CLAUDE.md exists in project root
- Covers: tech stack, file roles, test commands, deployment info, current focus
- Future Claude Code sessions start with project context

### Context
Phase 2 finding #4. Every session currently starts cold — 5-10 minutes wasted on orientation.

---

## Goal 4: Evaluate and Merge Security Branch
**Source:** Audit Phase 4, Move #3
**Category:** Foundational
**Priority:** 4 — free improvements already written

### Objective
Evaluate `origin/claude/security-code-audit-6k0Fg` and cherry-pick viable work (CI workflow, tests, refactoring).

### Success Criteria
- Branch contents reviewed for quality and compatibility
- Useful work cherry-picked or adapted into main
- Branch deleted or documented as superseded
- No regressions in existing tests

### Context
Phase 2 finding #3. Branch contains: CI workflow, 30 additional tests, robustness pass, refactoring. Never merged — status unknown.

---

## Goal 5: Add CI/CD with Green README Badge
**Source:** Audit Phase 4, Move #2
**Category:** Foundational
**Priority:** 5 — portfolio credibility signal

### Objective
Set up GitHub Actions to run pytest on push/PR. Add a passing badge to README.

### Success Criteria
- `.github/workflows/ci.yml` runs pytest on push to main and on PRs
- Tests pass in CI
- Green badge visible in README.md
- Optionally: pip-audit for dependency scanning

### Context
Phase 2 finding #2. For a portfolio piece, a green CI badge signals engineering discipline. The security branch may have a usable CI workflow to start from.

---

## Goal 6: Add Linting and Type Checking Config
**Source:** Audit Phase 4, Move #4
**Category:** Foundational
**Priority:** 6 — cheap engineering discipline signal

### Objective
Configure ruff (linting/formatting) and mypy (type checking) in pyproject.toml.

### Success Criteria
- `ruff check .` passes or has only acknowledged exceptions
- `mypy` configured with reasonable strictness for the codebase
- Tool configs in pyproject.toml

### Context
Phase 2 finding #8. Code style is manually consistent but not enforced. Adding configs takes minutes and signals professional engineering practice.

---

## Goal 7: Surface Company Name in Main Flow
**Source:** Audit Phase 4, Move #5
**Category:** Double down
**Priority:** 7 — protect unique differentiator

### Objective
Move company name input from the collapsed sidebar into the main UI flow so branded PDF reports actually get branded.

### Success Criteria
- Company name input visible without opening sidebar
- PDF report still uses the input correctly
- Sidebar retains retailer filter (less critical to surface)
- UX doesn't feel cluttered

### Context
Phase 2 finding #5. The branded PDF is a unique differentiator (no competitor offers it), but the company name input is hidden in a collapsed sidebar. First-time users generate unbranded reports.

---

## Goal 8: Add Report Generator Tests
**Source:** Audit Phase 4, Move #7
**Category:** Double down
**Priority:** 8 — protect differentiators

### Objective
Add smoke tests for PDF and CSV report generation.

### Success Criteria
- Tests call `generate_pdf_report` and `generate_csv_report` with various inputs
- Tests verify output is non-empty and correct type (BytesIO for PDF, str for CSV)
- Edge cases: empty results, all-critical results, mixed severity
- No crashes from unexpected data shapes

### Context
Phase 2 finding #7. The PDF report (596 LOC) and CSV report (74 LOC) are completely untested. A crash at download time breaks a unique differentiator.

---

## Goal 9: TypedDict for validate_batch Return
**Source:** Audit Phase 4, Move #8
**Category:** Double down
**Priority:** 9 — code quality for portfolio

### Objective
Replace the untyped dict returned by `validate_batch` with a TypedDict (or dataclass).

### Success Criteria
- Central data structure has explicit type contract
- All consumers (app.py, pdf_report.py, csv_report.py) updated
- mypy passes with the new types
- No runtime behavior changes

### Context
Phase 2 finding #6. The validation data dict flows through the entire app but has no type safety. For a portfolio piece, this demonstrates Python type system fluency.

---

## Goal 10: Deduplicate PDF Report Rendering
**Source:** Audit Phase 4, Move #10
**Category:** Foundational
**Priority:** 10 — cleaner code for portfolio

### Objective
Consolidate `render_group_with_continuation` and `render_multi_issue_group` into a single function.

### Success Criteria
- One rendering function handles both cases
- ~80 lines of duplication removed
- PDF output unchanged (visual regression check)
- Existing behavior preserved

### Context
Phase 2 finding #10. Two nearly identical functions at pdf_report.py:375-455.

---

## Improvement History

### 2026-09-23 — Audit (health check only)
- **Findings:** 1 critical, 5 important, 4 nice-to-have
- **Top concerns:** Duplicate detection is quadratic and writes every other row number into every duplicate's message — 3,000 identical GTINs took 1.5s and 51 MB of message text, so a single 10,000-row POST can OOM the 512 MB Fly VM. ENVIRONMENT=production is never set, so /api/docs and /openapi.json are live on gtin.lailarallc.com (the 2026-05-22 decision is inert). Non-ASCII digits (e.g. superscript 2) pass isdigit() then crash int() with an unhandled 500; the cost section's "warning items" (7 on sample data) disagrees with the summary's Warnings (4).
- **Other:** Rate limiter keys on the proxy IP behind Cloudflare/Fly (likely one shared 10/min bucket; no 429 test despite FAILURES.md lesson); Fly deploy doesn't wait on CI and uses setup-flyctl@master; README still points at MsShawnP URLs and lists render.yaml; client-mode.yml comment says v0.2.1 but installs v0.2.2; Source Sans @font-face declares 400-700 on a static 400 woff2 (faux-bold 600). Manual security/code/data pass replaced automated reviews. 90 tests pass, ruff clean.
- **Action taken:** Audit only — no fixes this session
- **Next review:** 2026-12-22
