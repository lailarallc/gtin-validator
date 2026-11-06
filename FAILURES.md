# Failures Log

Record what didn't work and why, so we don't repeat mistakes.

## 2026-10-07: A HANDOFF entry about NUL bytes wrote real NUL bytes into HANDOFF.md

**What happened:** The 2026-10-07 HANDOFF entry was written by a Python script, and its text mentioned the escape sequence for a NUL character (backslash, x, 0, 0). The escaping went through a shell heredoc and then a Python string literal, and two real NUL bytes landed in the file. Git then treated HANDOFF.md as binary: commit e52ed39 shows `HANDOFF.md | Bin 4489 -> 6669 bytes`, and diffs of the file stopped working. A later session (2026-10-09) found it and replaced them with the text "U+0000".

**Why it failed:** Every layer of quoting is a chance for an escape sequence to get decoded. The intent was literal text; the result was the control character.

**How we caught it:** Not at commit time. The `Bin` marker in `git commit --stat` / `git show --stat` was visible but not read.

**Lesson:** In prose files, name control characters by code point ("U+0000"), never by an escape sequence. Before committing a docs change, read the stat line: `Bin` on a .md file means a control byte got in.

**Tags:** encoding, heredoc, escaping, handoff, git-binary

## 2026-05-22: slowapi rate limiting looked correct but was silently non-functional

**What happened:** The /improve pass added rate limiting with all the right pieces visible — `@limiter.limit("10/minute")` decorators, `app.state.limiter`, exception handler. But it created two separate Limiter instances (one in main.py, one in validate.py) and never added `SlowAPIMiddleware`. Rate limiting was completely inert.

**Why it failed:** slowapi requires three things connected together: a single shared Limiter, that Limiter on `app.state.limiter`, and `SlowAPIMiddleware` on the app. Having any subset silently does nothing — no errors, no warnings.

**How we caught it:** `/ce:code-review` found it. Manual testing wouldn't have caught it easily because the app works normally — it just doesn't enforce limits.

**Lesson:** When adding security controls that fail silently, always write a negative test that proves the control is active (e.g., send 11 requests and assert 429). Code review is the last line of defense for silent failures.

**Tags:** slowapi, rate-limiting, silent-failure, middleware, integration
