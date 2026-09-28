"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { FileUp, LoaderCircle, ShieldCheck, X } from "lucide-react";
import type { UploadReport } from "@/lib/types";

type Mode = "file" | "text";

const PLACEHOLDER = "Nome do executivo\nCargo atual\ncontato@email.com\n\nResumo da trajetória…";

export function CandidateUpload() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadReport | null>(null);

  const ready = mode === "file" ? file !== null : text.trim().length >= 80;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || pending) return;
    setPending(true);
    setError(null);
    const form = new FormData();
    if (mode === "file" && file) form.append("file", file);
    else form.append("text", text);
    if (name.trim()) form.append("name", name.trim());
    if (role.trim()) form.append("current_role", role.trim());

    const res = await fetch("/api/candidates", { method: "POST", body: form }).catch(() => null);
    const body = await res?.json().catch(() => null);
    setPending(false);
    if (!res?.ok) {
      setError(body?.message ?? "Não foi possível adicionar o currículo.");
      return;
    }
    setResult(body as UploadReport);
    setFile(null);
    setText("");
    setName("");
    setRole("");
    router.refresh();
  }

  function close() {
    setOpen(false);
    setResult(null);
    setError(null);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-medium text-paper"
      >
        <FileUp className="size-4" aria-hidden /> Adicionar currículo
      </button>
    );
  }

  const tabs: [Mode, string][] = [
    ["file", "Enviar arquivo"],
    ["text", "Colar texto"],
  ];

  return (
    <section aria-labelledby="upload-title" className="rounded-xl border border-rule bg-paper">
      <header className="flex items-start justify-between gap-4 border-b border-rule px-6 py-4">
        <div>
          <h2 id="upload-title" className="font-display text-lg font-semibold tracking-[-0.015em]">
            Adicionar currículo
          </h2>
          <p className="mt-0.5 text-sm text-ink-soft">
            PDF, TXT ou texto colado. Nome e contatos são separados em código antes da indexação.
          </p>
        </div>
        <button type="button" onClick={close} className="rounded p-1 text-muted hover:text-ink" aria-label="Fechar">
          <X className="size-4" />
        </button>
      </header>

      <div className="grid gap-8 px-6 py-6 lg:grid-cols-2">
        <form onSubmit={submit} className="space-y-4">
          <div role="tablist" className="flex gap-4 border-b border-rule text-sm">
            {tabs.map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={mode === id}
                onClick={() => setMode(id)}
                className={clsx(
                  "-mb-px border-b-2 pb-2",
                  mode === id ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {mode === "file" ? (
            <div
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setFile(e.dataTransfer.files[0] ?? null);
              }}
              onClick={() => input.current?.click()}
              className="grid cursor-pointer place-items-center rounded-lg border border-dashed border-rule px-4 py-8 text-center hover:border-ink"
            >
              <FileUp className="size-5 text-muted" aria-hidden />
              <p className="mt-2 text-sm">{file ? file.name : "Arraste o arquivo ou clique para escolher"}</p>
              <p className="mt-0.5 text-xs text-muted">PDF com texto selecionável ou TXT, até 2 MB</p>
              <p className="mt-3 max-w-xs text-xs leading-relaxed text-ink-soft">
                Perfil do LinkedIn: no perfil, clique em <strong>Mais</strong> e depois em{" "}
                <strong>Salvar em PDF</strong>. O formato é reconhecido automaticamente.
              </p>
              <input
                ref={input}
                type="file"
                accept=".pdf,.txt,.md,application/pdf,text/plain"
                className="sr-only"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          ) : (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, 20000))}
              rows={8}
              placeholder={PLACEHOLDER}
              className="w-full resize-y rounded-lg border border-rule px-3 py-2.5 text-sm leading-relaxed outline-none focus:border-ink"
            />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="text-ink-soft">Nome (opcional)</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={80}
                placeholder="Detectado automaticamente"
                className="mt-1 w-full rounded-md border border-rule px-3 py-2 outline-none focus:border-ink"
              />
            </label>
            <label className="text-sm">
              <span className="text-ink-soft">Cargo atual (opcional)</span>
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                maxLength={120}
                className="mt-1 w-full rounded-md border border-rule px-3 py-2 outline-none focus:border-ink"
              />
            </label>
          </div>

          {error && <p className="text-sm text-oxide">{error}</p>}
          <button
            type="submit"
            disabled={!ready || pending}
            className="inline-flex items-center gap-2 rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper disabled:opacity-50"
          >
            {pending && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
            {pending ? "Indexando…" : "Adicionar à base"}
          </button>
        </form>

        <div>{result ? <UploadResult result={result} /> : <UploadHint />}</div>
      </div>
    </section>
  );
}

function UploadHint() {
  return (
    <div className="grid h-full place-items-center rounded-lg bg-mist/60 px-6 py-8 text-center text-sm leading-relaxed text-ink-soft">
      Depois do envio, você vê aqui exatamente o que foi separado e o texto que o modelo vai ler. O
      currículo entra na busca imediatamente.
    </div>
  );
}

function UploadResult({ result }: { result: UploadReport }) {
  const stats: [number, string][] = [
    [result.pii_removed, "dados pessoais separados"],
    [result.chunks_indexed, "trechos indexados"],
    [result.gender_cues.length, "marcas de gênero neutralizadas"],
  ];
  return (
    <div className="animate-rise space-y-4" aria-live="polite">
      <p className="flex items-center gap-2 text-sm font-medium text-verdigris">
        <ShieldCheck className="size-4" aria-hidden />
        Currículo de {result.name} incluído na base
      </p>
      <dl className="grid grid-cols-3 gap-2 text-center">
        {stats.map(([value, label]) => (
          <div key={label} className="rounded-md bg-mist px-2 py-3">
            <dd className="font-mono text-xl">{value}</dd>
            <dt className="text-[11px] leading-tight text-muted">{label}</dt>
          </div>
        ))}
      </dl>
      <p className="text-xs leading-relaxed text-ink-soft">
        {result.source_format === "linkedin" &&
          "Exportação do LinkedIn reconhecida: resumo, experiências, formação e competências organizados. "}
        {result.name_detected ? "Nome detectado no documento. " : "Nome informado no formulário. "}
        {result.contacts_found.length
          ? `Encontrado(s): ${result.contacts_found.join(", ")}. Ficam no cadastro, fora do índice e fora do modelo.`
          : "Nenhum contato encontrado no texto."}
      </p>
      <div>
        <p className="text-xs font-medium text-ink-soft">O que o modelo vai ler</p>
        <p className="mt-1.5 max-h-56 overflow-auto rounded-md border border-rule bg-mist/50 px-3 py-2.5 font-serif text-[14px] leading-relaxed whitespace-pre-line text-ink-soft">
          {result.indexed_text}
        </p>
      </div>
    </div>
  );
}
