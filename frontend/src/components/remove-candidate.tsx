"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";

export function RemoveCandidate({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function remove() {
    if (!window.confirm(`Remover ${name} da base? O currículo sai do índice e do cadastro.`)) return;
    setPending(true);
    await fetch(`/api/candidates/${id}`, { method: "DELETE" }).catch(() => null);
    setPending(false);
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={remove}
      disabled={pending}
      className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-muted hover:text-oxide disabled:opacity-50"
    >
      <Trash2 className="size-3.5" aria-hidden /> Remover
    </button>
  );
}
