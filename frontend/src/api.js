import { API_BASE_URL } from "./config";

export async function analyzePr(prUrl) {
  const response = await fetch(`${API_BASE_URL}/analyze-pr?url=${encodeURIComponent(prUrl)}`);

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}
