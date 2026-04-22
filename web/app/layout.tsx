import "./globals.css";

import { AppShell } from "@/components/app-shell";
import { StaleChunkReload } from "@/components/stale-chunk-reload";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <StaleChunkReload />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
