const DEFAULT_API_ORIGIN = "http://localhost:5001";

function normalizeOrigin(origin: string): string {
  return origin.trim().replace(/\/+$/, "");
}

function toApiBase(originOrApiBase: string): string {
  const normalized = normalizeOrigin(originOrApiBase);
  return normalized.endsWith("/api") ? normalized : `${normalized}/api`;
}

const envOrigin = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export const API_BASE = envOrigin
  ? toApiBase(envOrigin)
  : toApiBase(DEFAULT_API_ORIGIN);

