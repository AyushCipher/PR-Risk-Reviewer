import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from app.services.github_fetcher import PRFetchError, fetch_pr_data, parse_pr_url


def test_parse_pr_url_valid():
    owner, repo, number = parse_pr_url("https://github.com/octocat/Hello-World/pull/11023")
    assert (owner, repo, number) == ("octocat", "Hello-World", 11023)


def test_parse_pr_url_with_trailing_path():
    owner, repo, number = parse_pr_url("https://github.com/octocat/Hello-World/pull/11023/files")
    assert (owner, repo, number) == ("octocat", "Hello-World", 11023)


def test_parse_pr_url_malformed_raises():
    with pytest.raises(PRFetchError) as exc_info:
        parse_pr_url("not-a-url")
    assert exc_info.value.status_code == 400


def test_parse_pr_url_not_a_pull_request_link_raises():
    with pytest.raises(PRFetchError):
        parse_pr_url("https://github.com/octocat/Hello-World/issues/5")


# --- Integration tests against real, small, public PRs (network required) ---
# These tests hit the real GitHub API. Run them locally but not in CI.


@pytest.mark.e2e
def test_fetch_real_pr_with_single_added_file():
    data = fetch_pr_data("https://github.com/octocat/Hello-World/pull/11023")
    assert data["repo"] == "octocat/Hello-World"
    assert data["pr_number"] == 11023
    assert data["title"]
    assert len(data["files"]) == 1
    assert data["files"][0]["filename"] == "README.md"
    assert data["files"][0]["status"] == "added"


@pytest.mark.e2e
def test_fetch_real_pr_with_modified_file():
    data = fetch_pr_data("https://github.com/octocat/Spoon-Knife/pull/41111")
    assert data["repo"] == "octocat/Spoon-Knife"
    filenames = {f["filename"] for f in data["files"]}
    assert "index.html" in filenames


@pytest.mark.e2e
def test_fetch_real_pr_with_no_file_changes():
    data = fetch_pr_data("https://github.com/octocat/Hello-World/pull/11005")
    assert data["pr_number"] == 11005
    assert data["files"] == []


@pytest.mark.e2e
def test_fetch_nonexistent_pr_raises_404():
    with pytest.raises(PRFetchError) as exc_info:
        fetch_pr_data("https://github.com/octocat/Hello-World/pull/999999")
    assert exc_info.value.status_code == 404



# --- Hardening: simulated failure modes (no live network needed) ---


class _FakeResponse:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.headers = headers or {}
        self.text = str(self._json_data)

    def json(self):
        return self._json_data


class _FakeClientBase:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeRateLimitedClient(_FakeClientBase):
    def get(self, path, params=None):
        return _FakeResponse(403, headers={"X-RateLimit-Remaining": "0"})


def test_rate_limit_on_pr_lookup_raises_429(monkeypatch):
    import app.services.github_fetcher as module

    monkeypatch.setattr(module.httpx, "Client", _FakeRateLimitedClient)
    with pytest.raises(PRFetchError) as exc_info:
        fetch_pr_data("https://github.com/octocat/Hello-World/pull/1")
    assert exc_info.value.status_code == 429


class _FakeUnreachableClient(_FakeClientBase):
    def get(self, path, params=None):
        raise httpx.ConnectError("connection refused")


def test_network_failure_raises_502(monkeypatch):
    import app.services.github_fetcher as module

    monkeypatch.setattr(module.httpx, "Client", _FakeUnreachableClient)
    with pytest.raises(PRFetchError) as exc_info:
        fetch_pr_data("https://github.com/octocat/Hello-World/pull/1")
    assert exc_info.value.status_code == 502


class _FakePaginatedClient(_FakeClientBase):
    def get(self, path, params=None):
        if path.endswith("/files"):
            per_page = (params or {}).get("per_page", 100)
            files = [
                {
                    "filename": f"file_{i}.py",
                    "status": "modified",
                    "patch": "+x",
                    "additions": 1,
                    "deletions": 0,
                }
                for i in range(per_page)
            ]
            return _FakeResponse(200, json_data=files)
        return _FakeResponse(200, json_data={"title": "huge PR"})


def test_unusually_large_diff_is_capped_not_hung(monkeypatch):
    import app.services.github_fetcher as module

    monkeypatch.setattr(module.httpx, "Client", _FakePaginatedClient)
    data = fetch_pr_data("https://github.com/octocat/Hello-World/pull/1")
    assert len(data["files"]) == module._MAX_FILES


class _FakeUnauthorizedPrivateRepoClient(_FakeClientBase):
    def get(self, path, params=None):
        return _FakeResponse(404, json_data={"message": "Not Found"})


def test_private_repo_without_token_raises_404(monkeypatch):
    import app.services.github_fetcher as module

    monkeypatch.setattr(module.httpx, "Client", _FakeUnauthorizedPrivateRepoClient)
    with pytest.raises(PRFetchError) as exc_info:
        fetch_pr_data("https://github.com/some-org/private-repo/pull/1")
    assert exc_info.value.status_code == 404
    assert "private" in str(exc_info.value).lower()
