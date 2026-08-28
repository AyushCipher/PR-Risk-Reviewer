from __future__ import annotations

"""Placeholder GitHub PR fetcher used until the real fetcher is wired in.

Returns data matching the shared /fetch-pr response shape documented in
docs/interfaces.md. Swap the import in app/routers/analyze_pr.py for
app.services.github_fetcher.fetch_pr_data once that module is available -
the return shape is identical, so no other code needs to change.
"""

import re

_PR_URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")

_SAMPLE_FILES = [
    {
        "filename": "backend/app/services/auth_middleware.py",
        "status": "modified",
        "patch": (
            "@@ -10,6 +10,12 @@\n"
            "+def authenticate(request):\n"
            "+    token = request.headers.get('Authorization')\n"
            "+    session['user'] = decode_token(token)\n"
            "+    return session['user']\n"
        ),
        "additions": 12,
        "deletions": 0,
    },
    {
        "filename": "backend/migrations/0012_add_role_column.py",
        "status": "added",
        "patch": (
            "@@ -0,0 +1,3 @@\n"
            "+def upgrade():\n"
            "+    op.execute('ALTER TABLE users ADD COLUMN role TEXT')\n"
        ),
        "additions": 3,
        "deletions": 0,
    },
    {
        "filename": ".env.production",
        "status": "modified",
        "patch": "@@ -1,2 +1,3 @@\n+STRIPE_SECRET_KEY=example_placeholder_not_a_real_key_00000\n",
        "additions": 1,
        "deletions": 0,
    },
]


def fetch_pr_data(url: str) -> dict:
    match = _PR_URL_RE.search(url)
    if not match:
        raise ValueError(f"not a recognizable GitHub PR URL: {url}")

    owner, repo, pr_number = match.groups()
    return {
        "pr_url": url,
        "repo": f"{owner}/{repo}",
        "pr_number": int(pr_number),
        "title": f"Mock PR #{pr_number} for {owner}/{repo}",
        "files": _SAMPLE_FILES,
    }
