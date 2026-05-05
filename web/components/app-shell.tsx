"use client";

import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  // 应用外壳只负责全局氛围层和顶部品牌区，具体页面内容通过 children 注入。
  return (
    <div className="app-shell">
      <div className="app-shell__glow app-shell__glow--left" aria-hidden="true" />
      <div className="app-shell__glow app-shell__glow--right" aria-hidden="true" />

      <div className="app-shell__inner">
        <header className="app-topbar">
          <div className="app-brand">
            <div className="app-brand__mark">DX</div>
            <div>
              <div className="app-brand__title">DeepExcel 质量分析演示</div>
            </div>
          </div>
        </header>

        <div className="app-main">{children}</div>
      </div>
    </div>
  );
}
