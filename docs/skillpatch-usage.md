# SkillPatch usage

**Skill installed:** [`code-review`](https://skillpatch.dev/skills/code-review-4) (slug: `code-review-4`), published by CodeRabbit, domains `development`/`testing`, verified, security score 95.

The skill file is installed at [`skills/code-review/SKILL.md`](../skills/code-review/SKILL.md).

## Why this skill

Browsing the catalog at `skillpatch.dev/skills` for something code-review-relevant, `code-review-4` was the closest direct fit for a project literally named PR Risk Reviewer: it defines a workflow for finding bugs, security issues, and quality risks in changed code, and grouping the findings by severity (Critical, Warning, Info) - the same severity-first framing this project's own `/analyze-pr` output uses (`low`/`medium`/`high`).

## How it was actually used

The skill's primary workflow drives the CodeRabbit CLI (`coderabbit review --agent`), which requires installing that CLI and authenticating with a CodeRabbit account. Neither was available in the build environment (no CLI install, no account), so the CLI itself was not invoked - that's a real limitation, not glossed over here.

What was done instead: the skill's documented review criteria (severity grouping, "find bugs / security issues / quality risks") were applied manually as a self-review pass over the frontend code in this stage, before committing. That pass produced one concrete fix:

- **Warning-level finding:** `frontend/src/api.js`'s `analyzePr()` call had no request timeout. If the backend hung, the UI would sit in the loading state indefinitely with no way out. Fixed by adding an `AbortController`-based 20s timeout that surfaces a clear error message instead.

No Critical-level findings (no secrets, no injection paths - the only user input is passed straight to `encodeURIComponent` and never rendered as HTML) or other Warning-level issues turned up in this pass.
