# Interfaces

Shared response and data shapes for PR Risk Reviewer. Build against these
exactly - field names and types should not drift without updating this file.

## `GET /fetch-pr?url=<github_pr_url>`

Owned by the GitHub fetcher module. Response:

```json
{
  "pr_url": "string",
  "repo": "owner/repo",
  "pr_number": 123,
  "title": "string",
  "files": [
    {
      "filename": "path/to/file.py",
      "status": "modified",
      "patch": "diff hunk text",
      "additions": 10,
      "deletions": 2
    }
  ]
}
```

`files[].patch` is a unified-diff hunk (the `patch` field from the GitHub
API), with added lines prefixed `+` and removed lines prefixed `-`.

## Heuristics flag (internal)

Produced by `app/services/heuristics.py` from a `files` array in the shape
above. Not exposed directly over HTTP - consumed by the LLM explainer and
the aggregation endpoint.

```json
{
  "file": "string",
  "hunk": "string",
  "tag": "auth_change|migration|config_change|hardcoded_secret|missing_test",
  "matched_reason": "string"
}
```

## `GET /analyze-pr?url=<github_pr_url>`

Combines the fetcher, heuristics engine, and LLM explainer. Response:

```json
{
  "pr_url": "string",
  "overall_risk_score": 0,
  "flags": [
    {
      "file": "string",
      "tag": "string",
      "severity": "low|medium|high",
      "explanation": "string",
      "matched_reason": "string",
      "hunk_excerpt": "string"
    }
  ]
}
```

`overall_risk_score` is a weighted sum by severity (high=25, medium=10,
low=3), capped at 100.

Errors: a malformed or unrecognized PR URL returns HTTP 400 with a `detail`
message.
