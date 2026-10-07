# Decisions Log

## 2026-10-07: Own-data results are summary-only; the server enforces it

**Decision:** The free app returns only `{ summary, score }` for the user's own data (paste or upload). Row-level detail, the analysis sections, and the CSV/PDF downloads exist only for the sample, via `POST /api/sample/validate`. The full report for your own file is the GTIN Validator Kit.

**Why:** The free app is the funnel to the GTIN Validator Kit. Hiding detail in the UI isn't a limit: anyone could read the JSON or call the report endpoints. So the server never builds or caches detail for own data.

**How it's enforced:** `/api/validate` and `/api/validate/upload` return `SummaryResponse`, store nothing in the cache, and issue no token. Only `/api/sample/validate` stores a result and issues a token, so the report and completeness endpoints can only ever serve the sample. Any other token returns 404 ("Validation result expired or not found."). `tests_api.py` locks the exact own-data keys and the 404.

**Scope:** `backend/routes/validate.py`, `backend/schemas/responses.py`, the frontend results screens. `gtin_core.py` is unchanged; the engine computes the same full result and the route discards everything but summary and score.

**Do not:** Return a token, `results`, or any other `ValidationResponse` field from an own-data endpoint, or cache own-data results, even to support a "nicer" feature. Gate by not producing the data, not by hiding it in the UI.

## 2026-09-02: Hosting is Fly.io; Render is retired

**Decision:** gtin-validator is hosted on Fly.io. Render is retired.

**Why:** Migrated off Render during the org migration. Deploys run through `.github/workflows/fly-deploy.yml` (Fly.io, app `gtin-validator`, region `iad`). Render was verified empty and `render.yaml` was orphaned dead config, so it was removed.

**Scope:** Deployment/hosting for gtin-validator. Live URL `https://gtin.lailarallc.com`. (Note: some older decisions and prose files above/elsewhere still reference "Render free tier" as historical rationale — that context predates this migration.)

**Do not:** Re-add `render.yaml` or reintroduce Render references as live config. Stale `onrender.com` mentions in prose files are historical, not current deployment.

## 2026-05-22: Use shared module pattern for cross-file framework singletons

**Decision:** Any framework object that must be the same instance across modules (Limiter, metrics collectors, etc.) lives in its own module and is imported everywhere.

**Why:** Creating separate instances of slowapi Limiter in different files caused rate limiting to silently fail. The decorators used an orphan instance disconnected from the app. slowapi gives zero feedback when misconfigured.

**Scope:** `backend/limiter.py` is the canonical example. Apply the same pattern to any future cross-cutting concern that requires a single shared instance.

**Do not:** Instantiate framework singletons locally in route files. If you see `Limiter(...)` in a routes file, it's wrong.

## 2026-05-22: Disable Swagger/ReDoc in production via ENVIRONMENT env var

**Decision:** Conditionally disable `/api/docs` and `/api/redoc` when `ENVIRONMENT=production`.

**Why:** API docs expose the full endpoint schema to anyone. Useful in dev, unnecessary risk in production.

**Scope:** `backend/main.py` — `docs_url` and `redoc_url` set to `None` when `ENVIRONMENT=production`.

**Do not:** Use a separate config file or settings module for this — a single env var check is sufficient for this project's scale.

## 2026-05-22: Use slowapi for rate limiting at 10 req/min per IP

**Decision:** Add slowapi rate limiting to the validate and upload endpoints at 10 requests/minute per IP address.

**Why:** Validate and upload endpoints are CPU-intensive (parsing files, running validation on up to 10K GTINs). On Render free tier, unbounded requests could exhaust the instance.

**Scope:** `/api/validate` and `/api/validate/upload` endpoints.

**Do not:** Move rate limiting to nginx/reverse proxy level — Render free tier doesn't support custom nginx config.

## 2026-05-15: Migrate from Streamlit to FastAPI + React

**Decision:** Replace the Streamlit UI entirely with a React 19 + TypeScript SPA backed by a FastAPI API. Core validation engine (`gtin_core.py`) stays unchanged.

**Why:** Streamlit's rerun model causes full-page reloads on every interaction, slow initial load, and clunky UX. For a portfolio piece targeting operations teams, the UI needs to feel professional and responsive.

**Alternatives considered:**
- **Gradio** — same rerun model problem as Streamlit
- **Keep Streamlit, optimize** — fundamental architecture limitation, not a tuning problem
- **Incremental migration** — rejected in favor of clean replacement since the core engine is decoupled

**Key sub-decisions:**
- **No component library** (MUI, Chakra) — the existing design is distinctive, a library would fight it and add 200KB+ bundle weight. CSS Modules with custom property tokens instead.
- **No router** — single-page tool with phase-based rendering (idle → loading → results), not a multi-page app.
- **useReducer over Redux/Zustand** — 8 state variables, linear workflow, no global store needed.
- **Scroll-spy sidebar over tabs** — 10 analysis sections are too many for tabs. IntersectionObserver highlights active section as user scrolls.
- **Single deploy** — FastAPI serves both API and SPA static files from one Docker container on Render free tier.
- **In-memory cache** — dict with 30-min TTL for validation results, keyed by UUID token. Report downloads use the token to avoid re-validation.

## 2026-05-15: Consolidate PDF rendering functions

**Decision:** Merge `render_group_with_continuation` and `render_multi_issue_group` into a single `render_item_group` function with optional `recommendation_text` parameter.

**Why:** ~80 lines of near-identical pagination logic. One function handles both cases with a conditional header height.

## 2026-05-16: Never expose raw exceptions in API error responses

**Decision:** Backend error handlers must return user-friendly messages to the client. Raw Python exceptions (`str(exc)`, `f"...{exc}"`) must not appear in HTTPException detail strings.

**Why:** A prospect uploading a malformed file saw Python stack traces in the UI error banner, undermining credibility. Friendly messages for the client; full details logged server-side.

**Scope:** All backend error handlers in `backend/routes/`.

**Do not:** Use `f"...{exc}"` or `str(exc)` in HTTPException detail messages. Log the real exception with `logger.error()` or let it propagate to FastAPI's default 500 handler.
