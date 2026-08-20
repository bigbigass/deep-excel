"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const investigationActive = pathname.startsWith("/investigations");

  return (
    <div className="app-shell">
      <div className="app-shell__glow app-shell__glow--left" aria-hidden="true" />
      <div className="app-shell__glow app-shell__glow--right" aria-hidden="true" />

      <div className="app-shell__inner">
        <header className="app-topbar">
          <Link className="app-brand" href="/investigations/new">
            <div className="app-brand__mark">DX</div>
            <div>
              <div className="app-brand__title">DeepExcel 质量调查</div>
              <div className="app-brand__subtitle">Evidence-driven quality investigation</div>
            </div>
          </Link>

          <nav className="app-nav" aria-label="主要功能">
            <Link
              className={investigationActive ? "app-nav__link app-nav__link--active" : "app-nav__link"}
              href="/investigations/new"
            >
              质量调查
            </Link>
            <Link
              className={!investigationActive ? "app-nav__link app-nav__link--active" : "app-nav__link"}
              href="/"
            >
              报告演示
            </Link>
          </nav>
        </header>

        <div className="app-main">{children}</div>
      </div>
    </div>
  );
}
