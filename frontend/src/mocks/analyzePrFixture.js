export const analyzePrFixture = {
  pr_url: "https://github.com/octocat/Hello-World/pull/11023",
  overall_risk_score: 63,
  flags: [
    {
      file: "backend/app/services/auth_middleware.py",
      tag: "auth_change",
      severity: "high",
      explanation:
        "Sets session state directly from a decoded token without validating expiry or signature freshness.",
      matched_reason: "filename matches auth-related pattern: backend/app/services/auth_middleware.py",
      hunk_excerpt:
        "@@ -10,6 +10,12 @@\n+def authenticate(request):\n+    token = request.headers.get('Authorization')\n+    session['user'] = decode_token(token)\n+    return session['user']",
    },
    {
      file: ".env.production",
      tag: "hardcoded_secret",
      severity: "high",
      explanation:
        "A production API key is committed directly in the diff instead of being pulled from a secrets manager.",
      matched_reason: "diff line looks like a hardcoded credential: STRIPE_SECRET_KEY=...",
      hunk_excerpt: "@@ -1,2 +1,3 @@\n+STRIPE_SECRET_KEY=example_placeholder_not_a_real_key_00000",
    },
    {
      file: "backend/migrations/0012_add_role_column.py",
      tag: "migration",
      severity: "medium",
      explanation:
        "Adds a new column to the users table with no default value, which can fail on large existing tables.",
      matched_reason: "file located in a migrations folder: backend/migrations/0012_add_role_column.py",
      hunk_excerpt: "@@ -0,0 +1,3 @@\n+def upgrade():\n+    op.execute('ALTER TABLE users ADD COLUMN role TEXT')",
    },
    {
      file: "backend/app/services/auth_middleware.py",
      tag: "missing_test",
      severity: "low",
      explanation: "The new authenticate function has no accompanying unit test in this PR.",
      matched_reason: "new/changed function 'authenticate' added with no test file touched in this PR",
      hunk_excerpt:
        "@@ -10,6 +10,12 @@\n+def authenticate(request):\n+    token = request.headers.get('Authorization')",
    },
  ],
};

export const emptyAnalyzePrFixture = {
  pr_url: "https://github.com/octocat/Hello-World/pull/11005",
  overall_risk_score: 0,
  flags: [],
};
