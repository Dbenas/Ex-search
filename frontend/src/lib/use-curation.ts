"use client";

import { useCallback, useRef, useState } from "react";
import type { MatchReport, ScoreWeights, StageEvent, StreamEvent } from "./types";

type Status = "idle" | "running" | "done" | "error";

// EventSource only supports GET, so the POST response body is parsed manually.
async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) yield JSON.parse(data) as StreamEvent;
    }
  }
}

export function useCuration() {
  const [status, setStatus] = useState<Status>("idle");
  const [stages, setStages] = useState<StageEvent[]>([]);
  const [report, setReport] = useState<MatchReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  const run = useCallback(async (jobDescription: string, weights?: ScoreWeights) => {
    controller.current?.abort();
    controller.current = new AbortController();
    setStatus("running");
    setStages([]);
    setReport(null);
    setError(null);

    try {
      const res = await fetch("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: jobDescription, weights }),
        signal: controller.current.signal,
      });
      if (!res.ok || !res.body) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.message ?? "Não foi possível iniciar a análise.");
      }
      for await (const event of readEvents(res.body)) {
        if (event.type === "stage") setStages((prev) => [...prev, event]);
        else if (event.type === "report") {
          setReport(event.report);
          setStatus("done");
        } else throw new Error(event.message);
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError((err as Error).message);
      setStatus("error");
    }
  }, []);

  return { status, stages, report, error, run };
}
