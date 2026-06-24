export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string) || "http://localhost:8000";
export const WS_BASE_URL =
  (import.meta.env.VITE_WS_BASE_URL as string) || "ws://localhost:8000";
export const API_PREFIX = "/api/v1";
export const APP_NAME = "Lumira";
