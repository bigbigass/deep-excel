import "./globals.css";

import { AppShell } from "@/components/app-shell";
import { StaleChunkReload } from "@/components/stale-chunk-reload";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // 在最外层统一包裹应用壳和陈旧 chunk 自动刷新逻辑，避免各页面重复接入。
  return (
    <html lang="zh-CN">
      <body>
        <StaleChunkReload />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
