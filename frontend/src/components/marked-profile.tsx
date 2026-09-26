import type { Evidence } from "@/lib/types";

type Segment = { text: string; evidence: number[] };

// Splits the CV into plain and highlighted runs. Overlapping evidence spans are
// allowed: each run records every evidence index that covers it.
export function segmentProfile(text: string, evidence: Evidence[]): Segment[] {
  const cuts = new Set([0, text.length]);
  evidence.forEach((e) => {
    if (e.verified && e.start !== null && e.end !== null) {
      cuts.add(e.start);
      cuts.add(e.end);
    }
  });
  const points = [...cuts].sort((a, b) => a - b);
  const segments: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [from, to] = [points[i], points[i + 1]];
    const covering = evidence.flatMap((e, idx) =>
      e.verified && e.start !== null && e.end !== null && e.start <= from && e.end >= to
        ? [idx]
        : [],
    );
    segments.push({ text: text.slice(from, to), evidence: covering });
  }
  return segments;
}

type Props = { text: string; evidence: Evidence[]; active: number | null };

export function MarkedProfile({ text, evidence, active }: Props) {
  return (
    <p className="font-serif text-[15px] leading-[1.75] text-ink-soft">
      {segmentProfile(text, evidence).map((segment, i) =>
        segment.evidence.length ? (
          <mark
            key={i}
            className="mark-verified text-ink"
            data-active={active !== null && segment.evidence.includes(active)}
          >
            {segment.text}
          </mark>
        ) : (
          <span key={i}>{segment.text}</span>
        ),
      )}
    </p>
  );
}
