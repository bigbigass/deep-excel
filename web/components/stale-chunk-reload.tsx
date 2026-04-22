"use client";

import { useEffect } from "react";

const STALE_CHUNK_RELOAD_KEY = "deepexcel:stale-chunk-reload-at";
const STALE_CHUNK_RELOAD_WINDOW_MS = 30_000;

function stringifyErrorValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }

  if (value instanceof Error) {
    return `${value.name} ${value.message}`;
  }

  if (typeof value === "object" && value !== null) {
    return Object.values(value)
      .filter((entry) => typeof entry === "string")
      .join(" ");
  }

  return "";
}

export function shouldHandleStaleChunkAssetError(value: unknown): boolean {
  const text = stringifyErrorValue(value);

  return [
    "ChunkLoadError",
    "Loading chunk",
    "Failed to fetch dynamically imported module",
    "/_next/static/chunks/"
  ].some((pattern) => text.includes(pattern));
}

export function recoverFromStaleChunkOnce(
  storage: Pick<Storage, "getItem" | "setItem">,
  reload: () => void,
  now: number = Date.now()
): boolean {
  const previousReloadAtRaw = storage.getItem(STALE_CHUNK_RELOAD_KEY);
  const previousReloadAt = previousReloadAtRaw ? Number(previousReloadAtRaw) : null;
  if (previousReloadAt !== null && now - previousReloadAt < STALE_CHUNK_RELOAD_WINDOW_MS) {
    return false;
  }

  storage.setItem(STALE_CHUNK_RELOAD_KEY, String(now));
  reload();
  return true;
}

export function StaleChunkReload() {
  useEffect(() => {
    const handleWindowError = (event: ErrorEvent) => {
      if (!shouldHandleStaleChunkAssetError(event.error ?? event.message ?? event.filename)) {
        return;
      }

      recoverFromStaleChunkOnce(window.sessionStorage, () => window.location.reload());
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (!shouldHandleStaleChunkAssetError(event.reason)) {
        return;
      }

      recoverFromStaleChunkOnce(window.sessionStorage, () => window.location.reload());
    };

    window.addEventListener("error", handleWindowError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      window.removeEventListener("error", handleWindowError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  return null;
}
