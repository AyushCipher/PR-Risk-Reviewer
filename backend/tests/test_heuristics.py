import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.heuristics import (
    check_auth_change,
    check_config_change,
    check_hardcoded_secret,
    check_migration,
    check_missing_test,
    run_heuristics,
)


def test_auth_change_by_filename_includes_full_hunk_beyond_eight_lines():
    # Regression test: a real diff on this shape (jpadilla/pyjwt#1192) was
    # truncated to 8 lines, cutting off the `raise` that made the original
    # LLM explanation wrong - it looked like validation had been removed
    # when it had only been restructured.
    patch = (
        "@@ -426,9 +426,10 @@ def _validate_required_claims(\n"
        "        payload: dict[str, Any],\n"
        "        claims: Iterable[str],\n"
        "    ) -> None:\n"
        "-        for claim in claims:\n"
        "-            if payload.get(claim) is None:\n"
        "-                raise MissingRequiredClaimError(claim)\n"
        "+        missing_claims = [claim for claim in claims if payload.get(claim) is None]\n"
        "+\n"
        "+        if missing_claims:\n"
        "+            raise MissingRequiredClaimError(missing_claims[0], missing_claims)\n"
    )
    file = {"filename": "jwt/api_jwt.py", "patch": patch}
    flags = check_auth_change(file)
    assert len(flags) == 1
    assert "raise MissingRequiredClaimError(missing_claims[0]" in flags[0]["hunk"]


def test_auth_change_by_filename():
    file = {"filename": "backend/app/auth/middleware.py", "patch": "@@ -0,0 +1,3 @@\n+def check(): pass\n"}
    flags = check_auth_change(file)
    assert len(flags) == 1
    assert flags[0]["tag"] == "auth_change"
    assert "filename" in flags[0]["matched_reason"]


def test_auth_change_by_content():
    file = {
        "filename": "backend/app/routers/users.py",
        "patch": "@@ -1,2 +1,3 @@\n+def login(user):\n+    session['user'] = user\n",
    }
    flags = check_auth_change(file)
    assert len(flags) == 1
    assert flags[0]["tag"] == "auth_change"


def test_auth_change_no_match():
    file = {"filename": "backend/app/routers/health.py", "patch": "@@ -1 +1,2 @@\n+def health():\n+    return 'ok'\n"}
    assert check_auth_change(file) == []


def test_migration_by_path():
    file = {"filename": "backend/migrations/0007_add_users.py", "patch": "@@ -0,0 +1,2 @@\n+op.create_table('users')\n"}
    flags = check_migration(file)
    assert len(flags) == 1
    assert flags[0]["tag"] == "migration"


def test_migration_by_sql():
    file = {
        "filename": "backend/app/scripts/backfill.py",
        "patch": "@@ -1,1 +1,2 @@\n+cursor.execute('ALTER TABLE users ADD COLUMN age INT')\n",
    }
    flags = check_migration(file)
    assert len(flags) == 1
    assert "ALTER TABLE" in flags[0]["matched_reason"]


def test_migration_no_match():
    file = {"filename": "backend/app/services/report.py", "patch": "@@ -1 +1,2 @@\n+def build_report():\n+    return {}\n"}
    assert check_migration(file) == []


def test_config_change_by_filename():
    file = {"filename": ".env.production", "patch": "@@ -1 +1,2 @@\n+DEBUG=false\n"}
    flags = check_config_change(file)
    assert len(flags) == 1
    assert flags[0]["tag"] == "config_change"


def test_config_change_no_match():
    file = {"filename": "backend/app/services/report.py", "patch": "@@ -1 +1,2 @@\n+x = 1\n"}
    assert check_config_change(file) == []


def test_config_change_ignores_unrelated_yaml():
    file = {"filename": ".github/workflows/ci.yml", "patch": "@@ -1 +1,2 @@\n+run: pytest\n"}
    assert check_config_change(file) == []


def test_hardcoded_secret_detected():
    file = {
        "filename": "backend/app/services/client.py",
        "patch": "@@ -1 +1,2 @@\n+API_KEY = 'sk-abcdefgh12345678ijklmnop'\n",
    }
    flags = check_hardcoded_secret(file)
    assert len(flags) == 1
    assert flags[0]["tag"] == "hardcoded_secret"


def test_hardcoded_secret_no_match():
    file = {"filename": "backend/app/services/client.py", "patch": "@@ -1 +1,2 @@\n+x = 'short'\n"}
    assert check_hardcoded_secret(file) == []


def test_missing_test_flagged_when_no_test_file_touched():
    files = [
        {
            "filename": "backend/app/services/pricing.py",
            "patch": "@@ -0,0 +1,3 @@\n+def calculate_price(item):\n+    return item.base * 1.2\n",
        }
    ]
    flags = check_missing_test(files)
    assert len(flags) == 1
    assert flags[0]["tag"] == "missing_test"


def test_missing_test_not_flagged_when_test_file_touched():
    files = [
        {
            "filename": "backend/app/services/pricing.py",
            "patch": "@@ -0,0 +1,3 @@\n+def calculate_price(item):\n+    return item.base * 1.2\n",
        },
        {
            "filename": "backend/tests/test_pricing.py",
            "patch": "@@ -0,0 +1,2 @@\n+def test_calculate_price():\n+    assert True\n",
        },
    ]
    assert check_missing_test(files) == []


def test_missing_test_ignores_files_with_no_new_functions():
    files = [
        {"filename": "backend/app/services/constants.py", "patch": "@@ -1 +1,2 @@\n+MAX_RETRIES = 3\n"},
    ]
    assert check_missing_test(files) == []


def test_run_heuristics_combines_all_rules():
    files = [
        {"filename": "backend/app/auth/session.py", "patch": "@@ -0,0 +1,2 @@\n+def create_session(): pass\n"},
        {"filename": "backend/migrations/0001_init.py", "patch": "@@ -0,0 +1,1 @@\n+op.create_table('t')\n"},
    ]
    flags = run_heuristics(files)
    tags = {f["tag"] for f in flags}
    assert "auth_change" in tags
    assert "migration" in tags
    assert "missing_test" in tags
