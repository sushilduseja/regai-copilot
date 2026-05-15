# Domain Docs

## Layout

Single-context.

- `CONTEXT.md` at repo root — project domain language, key terms, and architectural context.
- `docs/adr/` at repo root — Architecture Decision Records.

## Consumer Rules

Skills like `improve-codebase-architecture`, `diagnose`, and `tdd` read `CONTEXT.md` to learn the project's domain language before making changes. They read `docs/adr/` to understand past architectural decisions and avoid contradicting them.

If `CONTEXT.md` does not exist yet, skills should note that and proceed without it.
