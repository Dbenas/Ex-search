"use client";

import { useState } from "react";
import clsx from "clsx";
import { FileDown, LoaderCircle } from "lucide-react";
import type { MatchReport } from "@/lib/types";

function slug(text: string) {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 40);
}

type Props = { report: MatchReport; className?: string };

// The PDF is rendered in the browser: the memo never travels to another service.
export function DownloadDossier({ report, className }: Props) {
  const [state, setState] = useState<"idle" | "working" | "error">("idle");

  async function download() {
    setState("working");
    try {
      const [{ pdf }, { DossierDocument }] = await Promise.all([
        import("@react-pdf/renderer"),
        import("./dossier-document"),
      ]);
      const now = new Date();
      const blob = await pdf(<DossierDocument report={report} generatedAt={now} />).toBlob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `parecer-${slug(report.job.role_title)}-${now.toISOString().slice(0, 10)}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  return (
    <button
      type="button"
      onClick={download}
      disabled={state === "working"}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-md border border-rule bg-paper px-3 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:border-ink hover:text-ink disabled:opacity-60",
        className,
      )}
    >
      {state === "working" ? (
        <LoaderCircle className="size-3.5 animate-spin" aria-hidden />
      ) : (
        <FileDown className="size-3.5" aria-hidden />
      )}
      {state === "working" ? "Gerando PDF…" : state === "error" ? "Falhou, tentar de novo" : "Baixar dossiê em PDF"}
    </button>
  );
}
