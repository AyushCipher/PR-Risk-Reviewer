import { API_BASE_URL } from "./config";

// ── PR Analysis (streaming) ───────────────────────────────────────────────────

/**
 * Submit a PR for analysis. Returns analysis_id immediately (non-blocking).
 * The Celery worker picks it up in the background.
 */
export async function submitPr(prUrl, githubToken = null) {
  const response = await fetch(`${API_BASE_URL}/analyses`, {
    method: "POST",
    credentials: "include",  // send session cookie
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pr_url: prUrl, github_token: githubToken }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Submit failed with status ${response.status}`);
  }

  const { analysis_id } = await response.json();
  return analysis_id;
}

/**
 * Opens an EventSource stream for the given analysis_id.
 * Calls callbacks as events arrive:
 *   onFlag(flag)              — called once per flag as it streams in
 *   onDone(overall_risk_score) — called when analysis is complete
 *   onError(message)          — called on error events or network failure
 */
export function streamAnalysis(analysisId, { onFlag, onDone, onError }) {
  const url = `${API_BASE_URL}/analyses/${analysisId}/stream`;
  const es = new EventSource(url, { withCredentials: true });

  es.addEventListener("flag", (e) => {
    try {
      onFlag(JSON.parse(e.data));
    } catch {
      // ignore malformed events
    }
  });

  es.addEventListener("done", (e) => {
    try {
      const { overall_risk_score } = JSON.parse(e.data);
      onDone(overall_risk_score);
    } catch {
      onDone(0);
    }
    es.close();
  });

  es.addEventListener("error", (e) => {
    try {
      const { detail } = JSON.parse(e.data);
      onError(detail || "An error occurred.");
    } catch {
      onError("Stream connection failed.");
    }
    es.close();
  });

  es.onerror = () => {
    onError("Lost connection to the server.");
    es.close();
  };

  // Return a cleanup function so callers can close the stream on unmount
  return () => es.close();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function getMe() {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    credentials: "include",
  });
  if (response.status === 401) return null;
  if (!response.ok) return null;
  return response.json();
}

export function loginWithGitHub() {
  window.location.href = `${API_BASE_URL}/auth/github`;
}

export function loginWithGoogle() {
  window.location.href = `${API_BASE_URL}/auth/google`;
}

export async function logout() {

  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// ── History ───────────────────────────────────────────────────────────────────

export async function getHistory() {
  const response = await fetch(`${API_BASE_URL}/analyses`, {
    credentials: "include",
  });
  if (response.status === 401) return null; // not logged in
  if (!response.ok) return [];
  return response.json();
}

export async function getAnalysis(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analyses/${analysisId}`, {
    credentials: "include",
  });
  if (!response.ok) return null;
  return response.json();
}

// ── Observability / Traces ───────────────────────────────────────────────────

export async function getTraces(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analyses/${analysisId}/traces`, {
    credentials: "include",
  });
  if (!response.ok) return null;
  return response.json();
}

