"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/", label: "Nova análise" },
  { href: "/candidatos", label: "Base de perfis" },
  { href: "/avaliacao", label: "Avaliação do modelo" },
];

export function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/login") return null;

  return (
    <header className="border-b border-rule bg-paper/80 backdrop-blur supports-[backdrop-filter]:bg-paper/70 sticky top-0 z-20">
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-8">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="font-display text-[19px] font-semibold tracking-[-0.02em]">Curadoria</span>
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            executive search
          </span>
        </Link>
        <nav className="flex gap-1 text-sm" aria-label="Principal">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={clsx(
                "rounded-md px-3 py-1.5 transition-colors",
                pathname === item.href
                  ? "bg-ink text-paper"
                  : "text-ink-soft hover:bg-mist hover:text-ink",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <p className="ml-auto hidden items-center gap-1.5 text-xs text-muted md:flex">
          <ShieldCheck className="size-3.5 text-verdigris" aria-hidden />
          O modelo recebe apenas perfis pseudonimizados
        </p>
      </div>
    </header>
  );
}
