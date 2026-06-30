const TOKEN_KEY = "forensiq_token";
const USER_KEY = "forensiq_user";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getUsername(): string | null {
  return sessionStorage.getItem(USER_KEY);
}

export function setAuth(token: string, username: string) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, username);
}

export function clearAuth() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}

/** Resolve artifact URLs with auth token for <img> tags. */
export function artifactUrl(path: string): string {
  const token = getToken();
  const normalized = path.startsWith("/api/artifacts/")
    ? path
    : path.replace(/^\/artifacts\//, "/api/artifacts/");
  if (!token) return normalized;
  const sep = normalized.includes("?") ? "&" : "?";
  return `${normalized}${sep}token=${encodeURIComponent(token)}`;
}

export function wsUrl(path: string): string {
  const token = getToken();
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const base = `${proto}://${window.location.host}${path}`;
  if (!token) return base;
  const sep = path.includes("?") ? "&" : "?";
  return `${base}${sep}token=${encodeURIComponent(token)}`;
}
