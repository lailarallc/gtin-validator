# Handoff

## Current State
**Phase:** Free app limit (PR #16) and paste fix (PR #17) live since 2026-10-09
**Branch:** main (main auto-deploys to Fly.io)
**CI:** 11 checks green on PR #17. Local: 99 tests (tests.py, test_golden.py, tests_api.py), ruff, mypy
**Live URL:** https://gtin.lailarallc.com

## 2026-11-06 — Wrap of the free-app-limit build session

**Started from:** The 2026-10-07 build session (PR #16), left open after the PR was opened.

**Did:** Kit v1.0.1 tag: checked before pushing and found Shawn had already pushed it on `fa3d3a5`; the release run succeeded and `GTIN-Validator-Kit.html` is published, so nothing was pushed from here. Pulled `main` (fast-forward only) in gtin-validator (switched off `free-app-limit` first), lailara-website (`reference/lailara-website/site`), and gtin-validator-kit. Stopped the local preview servers. No code changes.

**State:** main at ef1b840 (Fly scale-to-zero), clean. The local `free-app-limit` branch still exists; it was squash-merged as #16, so `git branch -d` refuses it and it needs `-D`. Not deleted.

**Next:** Optional: `git branch -D free-app-limit`. Next `/improve` due 2026-12-22. The 2026-09-23 audit findings (quadratic duplicate detection / OOM risk, `ENVIRONMENT=production` unset so `/api/docs` is live, non-ASCII digit 500, rate limiter keyed on the proxy IP) are still open.

---

## 2026-10-09 — Launch moved up; PR #16 and PR #17 merged

**What changed:** Shawn moved the kit launch up from 2026-10-16 to today. In order: the kit page (lailara-website #2) merged and verified live, the Payhip product switched from Unlisted to Visible, then PR #16 squash-merged (5e11aec).

**Live check after the 5e11aec deploy:** an own-data paste of 3 GTINs returned only `{ summary, score }` with no token, and the page showed the score, counts, and kit CTA. The sample returned the full report with a token (46 rows). The kit CTA's link (`?source=gtin-free`) loads the kit page, whose Buy link goes to https://payhip.com/b/orFhW. The Snapshot link loads /snapshot.

**Paste fix (PR #17, 46137e2):** GTINs pasted on one line were validated as one long, invalid GTIN. `split_gtin_entries` in gtin_core.py now splits pasted entries on line breaks, tabs, commas, and semicolons, and on spaces only when a part has 7+ digits, so a printed `0 36000 29145 2` stays one GTIN. Only `/api/validate` uses it; uploads are unchanged. Live: `036000291452 036000291453, 12345` on one line gives 3 GTINs, 2 critical.

**Also:** two NUL bytes in the 2026-10-07 entry made git treat this file as binary; they now read U+0000, and the file is stored with LF line endings like the rest of the repo.

**Next:** Nothing open for the free app. The kit (gtin-validator-kit) has the same paste box, still split on line breaks only; not changed.

---

## 2026-10-07 — Free app limit (launch Fri 2026-10-16)

**Started from:** Clean main. Task: limit the free app to score + counts for own data, keep the full report for the sample, point results at the GTIN Validator Kit.

**Did (one commit per step, see PLAN.md):**
1. Server: own-data `/api/validate` + `/api/validate/upload` return `{ summary, score }` only, no cache, no token. New `POST /api/sample/validate` returns the full report + token. Report/completeness endpoints 404 on any non-sample token. Rate limit (10/min) on all three, verified 11th call → 429.
2. Frontend: own-data results show ScoreCard + SummaryStats + kit CTA (critical / warnings-only / clean variants). Sample keeps the full report and email-gated downloads, with a sample CTA. Removed "free read" lines and `/services` links. Fixed `a.btn-primary` text going navy-on-navy on hover in the CTA.
3. Page copy: meta/og description, hero subtitle, "What you'll need" card.
4. Sample PDF: ● → •, ✓/✗ → PASS/FAIL, new closing paragraph. Also "unit → case" → "unit-to-case" in check names (fonts lack U+2192; gtin_core.py untouched). Extracted text has no U+25CF, U+2713, U+2717, or U+0000.
5. DECISIONS.md entry (summary-only, server-enforced), this handoff, PR opened.

**Didn't work / watch for:** A missing glyph extracts as `U+0000`, not as the character, so a text check that only looks for the original code points misses it. The PDF glyph check is a manual pypdf script, not a CI test (pypdf isn't a project dependency).

**State:** PR open on `free-app-limit`, not merged. `test_golden.py` unchanged and passing. Completeness endpoint now only reachable with a sample token, which returns 400 (sample has no product columns) — same as before for the sample; frontend never called it.

**Next:** On launch day (2026-10-16), once the kit is on Payhip and lailarallc.com/kits/gtin-validator is live: merge the PR, confirm the Fly deploy matches HEAD, then on the live site run one own-data paste and one sample run and check the kit links resolve.

---

## 2026-09-02 — Remove stale render.yaml + correct hosting refs

**Started from:** Fully-maintained project on main. Task: delete the orphaned `render.yaml` (dead config from the org migration — deploys run via CI, not Render).

**Did:** Verified real deploy path is `.github/workflows/fly-deploy.yml` (Fly.io) and that no CI workflow references `render.yaml`. `git rm render.yaml` (3b1059a), pushed, watched all 4 workflows go green. Separate commit (6ee384c): corrected stale "Render free tier" hosting line in CLAUDE.md → Fly.io, and fixed the `project_live_url` memory record + MEMORY.md index (Render → Fly.io). Prose files (README, PLAN, AUDIT, DECISIONS, docs/solutions) still carry historical "Render" mentions — deliberately out of scope this session.

**State:** render.yaml gone, main green on all 4 workflows, both commits pushed. CLAUDE.md + memory now say Fly.io (app `gtin-validator`/iad, https://gtin.lailarallc.com). No code touched — config/docs only.

**Next:** No feature work planned. Optional: sweep remaining prose files (README, PLAN, AUDIT, DECISIONS, docs/solutions) for stale Render references. Overdue maintenance: `/improve` (was due 2026-06-22) and dep audit (was due 2026-07-22) — both overdue, run when convenient.

---

## 2026-05-22 — Code review fix + dep audit + compound

**Started from:** /improve pass complete, but rate limiting implementation was non-functional.

**Did:** Fixed all 7 `/ce:code-review` findings (shared limiter module, SlowAPIMiddleware, type annotations, fillna filter, 429 in OpenAPI). Ran dep audit (0 vulnerabilities). Ran `/ce:compound` to document the rate limiting bug in `docs/solutions/integration-issues/`. Added `docs/solutions/` to CLAUDE.md.

**State:** 83 tests pass, ruff clean, mypy clean. All health tracker columns filled. Rate limiting functional. Pushed to main.

**Next:** No feature work planned. Next /improve due 2026-06-22, next dep audit due 2026-07-22.

---

## 2026-05-22 — Improvement pass

**Started from:** All planned work complete, PR #12 merged, deployed. No remaining tasks.

**Did:** Full `/improve` pass with security + correctness reviews. Fixed file upload row number bug, added security headers + rate limiting + non-root Docker user, tightened CORS, conditional API docs, full UUID cache tokens, expanded .gitignore, created FAILURES.md, deleted 7 stale branches, reconciled health tracker across all project directories.

**State:** 83 tests pass, ruff clean, mypy clean. New dep: slowapi. Health tracker now covers Active, Published, Reference, and Archived sections.

**Next:** Run dep audit (pip-audit + npm audit) to fill tracker column. Consider /ce:code-review. No feature work planned.

---

## 2026-05-16 — Audit v2 + Prospect-Readiness Fixes

**Started from:** Project shipped and stable post-migration. Preparing to show to a prospect.

**Did:**
- Full 4-phase audit (AUDIT.md) focused on prospect-demo readiness
- Implemented 7 fixes: page title + meta/OG tags, download error handling, error message sanitization, empty-paste feedback, filename sanitization, async/sync fix, API timeout
- All verified (tests, lint, typecheck, browser). PR #12 created.

**State:** PR #12 ready to merge. AUDIT.md and PLAN.md updated. No known bugs.

**Next:** Merge PR #12, verify live site after deploy, warm Render 2 min before prospect call.

## 2026-05-16 16:45 — Final checkpoint

**What changed:** Audit v2 complete, all 7 prospect-demo fixes in PR #12, ready to merge and demo.

**Why:** Session wrapped — all planned work done, PR created and pushed, tag `v2.0-audit-complete` applied.

**State:** PR #12 open and pushed. AUDIT.md (4 phases), PLAN.md (all tasks checked), DECISIONS.md (error message policy added), HANDOFF.md all current. No bugs, no loose ends.

**Next:** Merge PR #12, verify live deploy, warm Render before prospect call.

---

## Prior Session — 2026-05-15

1. Full migration from Streamlit to FastAPI + React (PR #6, squash-merged)
2. Fixed mypy CI failure (PR #7), consolidated PDF rendering (PR #6)
3. All 10 v1 audit goals complete, deployed to Render
4. UI polish: aligned download card buttons (PR #9), shortened button label (PR #10)
