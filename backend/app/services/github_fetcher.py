from __future__ import annotations

import os
import re
from typing import Optional

import httpx

GITHUB_API_BASE = "https://api.github.com"

_PR_URL_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)")

_PER_PAGE = 100
_MAX_FILES = 300


class PRFetchError(Exception):
    """A user-facing PR fetch failure, carrying an HTTP status code to surface."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def parse_pr_url(url: str) -> tuple[str, str, int]:
    match = _PR_URL_RE.match(url.strip())
    if not match:
        raise PRFetchError(f"not a recognizable GitHub PR URL: {url}", status_code=400)
    owner, repo, number = match.group(1), match.group(2), int(match.group(3))
    return owner, repo, number


def _auth_headers(token: Optional[str]) -> dict:
    resolved_token = token or os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if resolved_token:
        headers["Authorization"] = f"Bearer {resolved_token}"
    return headers


def _is_rate_limited(response: httpx.Response) -> bool:
    return response.headers.get("X-RateLimit-Remaining") == "0"


def _raise_for_pr_status(response: httpx.Response, owner: str, repo: str, number: int) -> None:
    if response.status_code == 200:
        return
    if response.status_code == 404:
        raise PRFetchError(
            f"pull request not found, or repo is private and no token was provided: "
            f"{owner}/{repo}#{number}",
            status_code=404,
        )
    if response.status_code == 401:
        raise PRFetchError("GitHub token was rejected (invalid or expired)", status_code=401)
    if response.status_code == 403 and _is_rate_limited(response):
        raise PRFetchError(
            "GitHub API rate limit exceeded; provide a GITHUB_TOKEN to raise the limit",
            status_code=429,
        )
    raise PRFetchError(
        f"GitHub API error {response.status_code}: {response.text[:200]}",
        status_code=502,
    )


def _fetch_all_files(client: httpx.Client, owner: str, repo: str, number: int) -> list[dict]:
    files: list[dict] = []
    page = 1
    while len(files) < _MAX_FILES:
        response = client.get(
            f"/repos/{owner}/{repo}/pulls/{number}/files",
            params={"per_page": _PER_PAGE, "page": page},
        )
        if response.status_code == 403 and _is_rate_limited(response):
            raise PRFetchError(
                "GitHub API rate limit exceeded; provide a GITHUB_TOKEN to raise the limit",
                status_code=429,
            )
        if response.status_code != 200:
            raise PRFetchError(
                f"GitHub API error {response.status_code}: {response.text[:200]}",
                status_code=502,
            )

        page_files = response.json()
        if not page_files:
            break

        for f in page_files:
            files.append({
                "filename": f.get("filename", ""),
                "status": f.get("status", ""),
                "patch": f.get("patch"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
            })
            if len(files) >= _MAX_FILES:
                break

        if len(page_files) < _PER_PAGE:
            break
        page += 1

    return files


def fetch_pr_data(url: str, token: Optional[str] = None) -> dict:
    owner, repo, number = parse_pr_url(url)
    headers = _auth_headers(token)

    try:
        with httpx.Client(base_url=GITHUB_API_BASE, headers=headers, timeout=15.0) as client:
            pr_response = client.get(f"/repos/{owner}/{repo}/pulls/{number}")
            _raise_for_pr_status(pr_response, owner, repo, number)
            pr_json = pr_response.json()
            files = _fetch_all_files(client, owner, repo, number)
    except httpx.RequestError as exc:
        raise PRFetchError(f"failed to reach GitHub API: {exc}", status_code=502) from exc

    return {
        "pr_url": url,
        "repo": f"{owner}/{repo}",
        "pr_number": number,
        "title": pr_json.get("title", ""),
        "files": files,
    }
