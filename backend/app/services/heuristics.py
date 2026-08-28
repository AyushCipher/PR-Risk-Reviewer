from __future__ import annotations

import re
from typing import TypedDict


class FileEntry(TypedDict, total=False):
    filename: str
    status: str
    patch: str
    additions: int
    deletions: int


class Flag(TypedDict):
    file: str
    hunk: str
    tag: str
    matched_reason: str


_AUTH_FILENAME_RE = re.compile(
    r"(auth|session|token|permission|middleware|jwt|oauth)", re.IGNORECASE
)
_AUTH_CONTENT_RE = re.compile(
    r"\b(jwt|oauth2?|session|authenticate|authorize|authorization|"
    r"permission|access[_-]?token|middleware)\b",
    re.IGNORECASE,
)

_MIGRATION_PATH_RE = re.compile(r"(^|/)migrations?(/|$)", re.IGNORECASE)
_MIGRATION_SQL_RE = re.compile(
    r"\b(ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE|DROP\s+COLUMN|ADD\s+COLUMN)\b",
    re.IGNORECASE,
)

_CONFIG_FILENAME_RE = re.compile(
    r"(^|/)\.env(\.[A-Za-z0-9_]+)?$"
    r"|(^|/)(settings|config)\.(py|json|ya?ml|js|ts)$"
    r"|(^|/)config/.*\.(py|json|ya?ml|js|ts)$",
    re.IGNORECASE,
)

_SECRET_KEYWORD_RE = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|access[_-]?key)", re.IGNORECASE
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"^['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*[:=]\s*"
    r"['\"]?([A-Za-z0-9_\-/+=]{16,})['\"]?,?\s*$"
)

_FUNC_DEF_RE = re.compile(
    r"^\+\s*(?:def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
    r"|(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
    r"|const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\()"
)

_TEST_FILENAME_RE = re.compile(
    r"(^|/)(test_\w+\.py|__tests__/.*)$|.*(_test\.py|\.test\.[jt]sx?|\.spec\.[jt]sx?)$",
    re.IGNORECASE,
)


def _patch_lines(patch: str) -> list[str]:
    return patch.splitlines() if patch else []


def _added_content_lines(patch: str) -> list[tuple[int, str]]:
    return [
        (i, line[1:])
        for i, line in enumerate(_patch_lines(patch))
        if line.startswith("+") and not line.startswith("+++")
    ]


def _excerpt(patch: str, index: int, context: int = 2) -> str:
    lines = _patch_lines(patch)
    start = max(0, index - context)
    end = min(len(lines), index + context + 1)
    return "\n".join(lines[start:end])


def _first_hunk(patch: str, max_lines: int = 8) -> str:
    return "\n".join(_patch_lines(patch)[:max_lines])


def check_auth_change(file: FileEntry) -> list[Flag]:
    filename = file.get("filename", "")
    patch = file.get("patch") or ""

    if _AUTH_FILENAME_RE.search(filename):
        return [{
            "file": filename,
            "hunk": _first_hunk(patch),
            "tag": "auth_change",
            "matched_reason": f"filename matches auth-related pattern: {filename}",
        }]

    for index, line in _added_content_lines(patch):
        match = _AUTH_CONTENT_RE.search(line)
        if match:
            return [{
                "file": filename,
                "hunk": _excerpt(patch, index),
                "tag": "auth_change",
                "matched_reason": f"diff content matches auth-related keyword: {match.group(0)}",
            }]
    return []


def check_migration(file: FileEntry) -> list[Flag]:
    filename = file.get("filename", "")
    patch = file.get("patch") or ""

    if _MIGRATION_PATH_RE.search(filename):
        return [{
            "file": filename,
            "hunk": _first_hunk(patch),
            "tag": "migration",
            "matched_reason": f"file located in a migrations folder: {filename}",
        }]

    for index, line in _added_content_lines(patch):
        match = _MIGRATION_SQL_RE.search(line)
        if match:
            return [{
                "file": filename,
                "hunk": _excerpt(patch, index),
                "tag": "migration",
                "matched_reason": f"diff contains schema-altering SQL: {match.group(0)}",
            }]
    return []


def check_config_change(file: FileEntry) -> list[Flag]:
    filename = file.get("filename", "")
    patch = file.get("patch") or ""

    if _CONFIG_FILENAME_RE.search(filename):
        return [{
            "file": filename,
            "hunk": _first_hunk(patch),
            "tag": "config_change",
            "matched_reason": f"filename matches config/settings pattern: {filename}",
        }]
    return []


def check_hardcoded_secret(file: FileEntry) -> list[Flag]:
    filename = file.get("filename", "")
    patch = file.get("patch") or ""
    flags: list[Flag] = []

    for index, line in _added_content_lines(patch):
        match = _SECRET_ASSIGNMENT_RE.match(line.strip())
        if match and _SECRET_KEYWORD_RE.search(match.group(1)):
            flags.append({
                "file": filename,
                "hunk": _excerpt(patch, index),
                "tag": "hardcoded_secret",
                "matched_reason": f"diff line looks like a hardcoded credential: {match.group(1)}=...",
            })
    return flags


def check_missing_test(files: list[FileEntry]) -> list[Flag]:
    flags: list[Flag] = []
    test_touched = any(_TEST_FILENAME_RE.search(f.get("filename", "")) for f in files)

    for file in files:
        filename = file.get("filename", "")
        if _TEST_FILENAME_RE.search(filename):
            continue
        patch = file.get("patch") or ""

        new_functions = []
        for index, line in enumerate(_patch_lines(patch)):
            match = _FUNC_DEF_RE.match(line)
            if match:
                name = next(g for g in match.groups() if g)
                new_functions.append((index, name))

        if new_functions and not test_touched:
            first_index, first_name = new_functions[0]
            flags.append({
                "file": filename,
                "hunk": _excerpt(patch, first_index),
                "tag": "missing_test",
                "matched_reason": (
                    f"new/changed function '{first_name}' added with no "
                    "test file touched in this PR"
                ),
            })

    return flags


def run_heuristics(files: list[FileEntry]) -> list[Flag]:
    flags: list[Flag] = []
    for file in files:
        flags.extend(check_auth_change(file))
        flags.extend(check_migration(file))
        flags.extend(check_config_change(file))
        flags.extend(check_hardcoded_secret(file))
    flags.extend(check_missing_test(files))
    return flags
