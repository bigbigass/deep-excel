import { recoverFromStaleChunkOnce, shouldHandleStaleChunkAssetError } from "../components/stale-chunk-reload";

test("stale chunk helper detects next asset mismatch messages", () => {
  expect(shouldHandleStaleChunkAssetError("ChunkLoadError: Loading chunk 123 failed")).toBe(true);
  expect(shouldHandleStaleChunkAssetError("http://127.0.0.1:3000/_next/static/chunks/app/page-0195843280fa9de7.js")).toBe(true);
  expect(shouldHandleStaleChunkAssetError(new Error("Failed to fetch dynamically imported module"))).toBe(true);
  expect(shouldHandleStaleChunkAssetError(new Error("network down"))).toBe(false);
});

test("stale chunk recovery only reloads once within the safety window", () => {
  const storage = {
    getItem: jest.fn().mockReturnValue(null),
    setItem: jest.fn()
  } as unknown as Storage;
  const reload = jest.fn();

  expect(recoverFromStaleChunkOnce(storage, reload, 1_000)).toBe(true);
  expect(storage.setItem).toHaveBeenCalledWith("deepexcel:stale-chunk-reload-at", "1000");
  expect(reload).toHaveBeenCalledTimes(1);

  (storage.getItem as jest.Mock).mockReturnValue("1000");
  expect(recoverFromStaleChunkOnce(storage, reload, 10_000)).toBe(false);
  expect(reload).toHaveBeenCalledTimes(1);
});
