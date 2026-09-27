import { Document, Page, StyleSheet, Text, View } from "@react-pdf/renderer";
import type { MatchReport, RankedCandidate, Recommendation } from "@/lib/types";

// Standard PDF fonts (Times, Helvetica) cover Portuguese without embedding files.
// They use WinAnsi encoding, so a few typographic symbols models like to emit are
// mapped to safe equivalents.
const UNSAFE: Record<string, string> = {
  "→": "->",
  "←": "<-",
  "≥": ">=",
  "≤": "<=",
  "≈": "~",
  "×": "x",
  "‑": "-",
  " ": " ",
};
const clean = (text: string) => text.replace(/[→←≥≤≈×‑ ]/g, (c) => UNSAFE[c] ?? c);

const C = {
  ink: "#0f1b2d",
  soft: "#3b4a5e",
  muted: "#6b7788",
  rule: "#d9dfe6",
  wash: "#eef1f4",
  verdigris: "#2f7d6d",
  amber: "#b7791f",
  oxide: "#a3412f",
};

const s = StyleSheet.create({
  page: {
    paddingTop: 56,
    paddingBottom: 64,
    paddingHorizontal: 58,
    fontFamily: "Times-Roman",
    fontSize: 10.5,
    lineHeight: 1.5,
    color: C.ink,
  },
  eyebrow: {
    fontFamily: "Helvetica",
    fontSize: 7.5,
    letterSpacing: 0.5,
    textTransform: "uppercase",
    color: C.muted,
  },
  h1: { fontFamily: "Helvetica-Bold", fontSize: 22, lineHeight: 1.2, marginTop: 6 },
  h2: { fontFamily: "Helvetica-Bold", fontSize: 13, marginBottom: 6 },
  h3: { fontFamily: "Helvetica-Bold", fontSize: 9, color: C.soft, marginTop: 10, marginBottom: 3 },
  lead: { fontSize: 12.5, lineHeight: 1.5, marginTop: 8 },
  body: { color: C.soft },
  small: { fontFamily: "Helvetica", fontSize: 8, color: C.muted, lineHeight: 1.4 },
  section: { marginTop: 22 },
  rule: { borderBottomWidth: 0.75, borderBottomColor: C.rule, marginVertical: 14 },
  bullet: { flexDirection: "row", marginBottom: 3 },
  bulletMark: { width: 12, color: C.muted },
  bulletText: { flex: 1, color: C.soft },
  chipRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
  chip: {
    fontFamily: "Helvetica",
    fontSize: 7.5,
    borderWidth: 0.75,
    borderColor: C.rule,
    borderRadius: 2,
    paddingHorizontal: 5,
    paddingVertical: 2,
    marginRight: 4,
    marginBottom: 4,
    color: C.soft,
  },
  footer: {
    position: "absolute",
    bottom: 30,
    left: 58,
    right: 58,
    fontFamily: "Helvetica",
    fontSize: 7,
    lineHeight: 1,
    color: C.muted,
  },
});

const RECOMMENDATION: Record<Recommendation, { label: string; color: string }> = {
  avancar: { label: "Avançar", color: C.verdigris },
  avancar_com_ressalvas: { label: "Avançar com ressalvas", color: C.amber },
  nao_priorizar: { label: "Não priorizar", color: C.muted },
};

const DIMENSIONS = [
  ["hard_skills", "Hard skills"],
  ["soft_skills", "Soft skills"],
  ["context_fit", "Fit de contexto"],
] as const;

function Bullets({ items, mark = "•" }: { items: string[]; mark?: string }) {
  return (
    <View>
      {items.map((item, i) => (
        <View key={i} style={s.bullet} wrap={false}>
          <Text style={s.bulletMark}>{mark === "#" ? `${i + 1}.` : mark}</Text>
          <Text style={s.bulletText}>{clean(item)}</Text>
        </View>
      ))}
    </View>
  );
}

function ScoreBar({ label, score, rationale }: { label: string; score: number; rationale: string }) {
  return (
    <View style={{ marginBottom: 7 }} wrap={false}>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 8.5 }}>{label}</Text>
        <Text style={{ fontFamily: "Courier", fontSize: 8.5 }}>{score}/10</Text>
      </View>
      <View style={{ height: 3, backgroundColor: C.wash, marginTop: 3, borderRadius: 2 }}>
        <View style={{ height: 3, width: `${score * 10}%`, backgroundColor: C.ink, borderRadius: 2 }} />
      </View>
      <Text style={[s.small, { marginTop: 3 }]}>{clean(rationale)}</Text>
    </View>
  );
}

function CandidateSection({ c }: { c: RankedCandidate }) {
  const rec = RECOMMENDATION[c.recommendation];
  const verified = c.evidence.filter((e) => e.verified);
  return (
    <View break style={{ paddingTop: 2 }}>
      <View style={{ flexDirection: "row", alignItems: "flex-start" }}>
        <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 30, lineHeight: 1, color: C.rule, width: 34 }}>
          {c.rank}
        </Text>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 16, lineHeight: 1.1 }}>{c.name}</Text>
          <Text style={[s.small, { fontSize: 9 }]}>{clean(c.current_role)}</Text>
          <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 8.5, color: rec.color, marginTop: 4 }}>
            {rec.label.toUpperCase()}
          </Text>
        </View>
        <View style={{ alignItems: "flex-end", width: 80 }}>
          <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 20, lineHeight: 1 }}>
            {Math.round(c.final_score)}
          </Text>
          <Text style={[s.small, { marginTop: 3 }]}>aderência / 100</Text>
        </View>
      </View>

      <Text style={[s.lead, { fontFamily: "Times-Italic" }]}>{clean(c.headline)}</Text>
      <Text style={[s.body, { marginTop: 8 }]}>{clean(c.analysis)}</Text>

      <View style={s.rule} />
      {DIMENSIONS.map(([key, label]) => (
        <ScoreBar key={key} label={label} score={c.scores[key].score} rationale={c.scores[key].rationale} />
      ))}

      <Text style={s.h3}>EVIDÊNCIAS CONFERIDAS NO CURRÍCULO</Text>
      {verified.map((e, i) => (
        <View key={i} style={{ marginBottom: 5 }} wrap={false}>
          <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 8.5 }}>{clean(e.requirement)}</Text>
          <Text style={s.body}>
            “{clean(e.quote)}”<Text style={s.small}> — {clean(e.claim)}</Text>
          </Text>
        </View>
      ))}
      {c.evidence.length > verified.length && (
        <Text style={s.small}>
          {c.evidence.length - verified.length} afirmação(ões) do modelo não encontrada(s) no currículo
          foram descartadas deste parecer.
        </Text>
      )}

      {c.gaps.length > 0 && (
        <>
          <Text style={s.h3}>SEM EVIDÊNCIA NO PERFIL</Text>
          <Bullets items={c.gaps} />
        </>
      )}
      {c.interview_focus.length > 0 && (
        <>
          <Text style={s.h3}>APROFUNDAR EM ENTREVISTA</Text>
          <Bullets items={c.interview_focus} mark="#" />
        </>
      )}
    </View>
  );
}

const COVERAGE = {
  lider: { label: "Coberto pelo 1º colocado", color: C.verdigris },
  outros: { label: "Só em perfis secundários", color: C.amber },
  ninguem: { label: "Sem evidência na base", color: C.oxide },
};

export function DossierDocument({ report, generatedAt }: { report: MatchReport; generatedAt: Date }) {
  const { job, metadata } = report;
  // Reports saved before coverage existed don't carry it.
  const coverage = report.coverage ?? [];
  const essentials = [...job.hard_requirements, ...job.soft_requirements].filter(
    (r) => r.importance === "essencial",
  );
  const date = generatedAt.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
  const weights = report.weights
    ? `${Math.round(report.weights.hard_skills * 100)}% hard skills, ${Math.round(report.weights.soft_skills * 100)}% soft skills e ${Math.round(report.weights.context_fit * 100)}% fit de contexto`
    : "40% hard skills, 30% soft skills e 30% fit de contexto";

  return (
    <Document
      title={`Parecer de shortlist · ${job.role_title}`}
      author="Curadoria Executiva"
      subject="Confidencial"
      creator="Curadoria Executiva"
    >
      <Page size="A4" style={s.page}>
        {/* Static on purpose: react-pdf drops dynamic (render) fixed text on pages
            created by forced breaks, so page numbers are omitted. */}
        <Text style={s.footer} fixed>
          Confidencial · uso restrito aos sócios · análise {metadata.run_id}
        </Text>
        <Text style={s.eyebrow}>Parecer de shortlist · {date}</Text>
        <Text style={s.h1}>{clean(job.role_title)}</Text>
        <Text style={s.lead}>{clean(job.mandate)}</Text>
        <Text style={[s.small, { marginTop: 6, fontSize: 9 }]}>{clean(job.company_context)}</Text>

        <View style={s.section}>
          <Text style={s.eyebrow}>Requisitos essenciais</Text>
          <View style={s.chipRow}>
            {essentials.map((r) => (
              <Text key={r.name} style={s.chip}>
                {clean(r.name)}
              </Text>
            ))}
          </View>
        </View>

        <View style={[s.section, { borderLeftWidth: 2, borderLeftColor: C.ink, paddingLeft: 14 }]}>
          <Text style={s.eyebrow}>Leitura do shortlist</Text>
          <Text style={s.lead}>{clean(report.executive_summary)}</Text>
        </View>

        <View style={s.section}>
          <Text style={s.h2}>Shortlist</Text>
          {report.top_candidates.map((c) => (
            <View key={c.candidate_id} style={{ flexDirection: "row", marginBottom: 5 }} wrap={false}>
              <Text style={{ fontFamily: "Helvetica-Bold", width: 16 }}>{c.rank}</Text>
              <View style={{ flex: 1 }}>
                <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 10 }}>
                  {c.name} <Text style={s.small}>· {clean(c.current_role)}</Text>
                </Text>
                <Text style={s.body}>{clean(c.headline)}</Text>
              </View>
              <Text style={{ fontFamily: "Helvetica-Bold", width: 30, textAlign: "right" }}>
                {Math.round(c.final_score)}
              </Text>
            </View>
          ))}
        </View>

        {report.next_steps.length > 0 && (
          <View style={s.section}>
            <Text style={s.h2}>Próximos passos</Text>
            <Bullets items={report.next_steps} mark="#" />
          </View>
        )}

        {report.top_candidates.map((c) => (
          <CandidateSection key={c.candidate_id} c={c} />
        ))}

        {(coverage.length > 0 || report.search_plan) && (
          <View break>
            {coverage.length > 0 && (
              <View>
                <Text style={s.h2}>Cobertura dos requisitos essenciais</Text>
                {coverage.map((r) => (
                  <View
                    key={r.requirement}
                    style={{ flexDirection: "row", paddingVertical: 3, borderBottomWidth: 0.5, borderBottomColor: C.rule }}
                    wrap={false}
                  >
                    <Text style={{ flex: 1 }}>{clean(r.requirement)}</Text>
                    <Text style={{ fontFamily: "Helvetica", fontSize: 8, color: COVERAGE[r.status].color }}>
                      {COVERAGE[r.status].label}
                      {r.status === "outros" ? `: ${r.covered_by.join(", ")}` : ""}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {report.search_plan && (
              <View style={s.section}>
                <Text style={s.h2}>Plano de busca</Text>
                <Text style={s.body}>{clean(report.search_plan.diagnosis)}</Text>
                {report.search_plan.target_profiles.map((t) => (
                  <View key={t.archetype} style={{ marginTop: 9 }} wrap={false}>
                    <Text style={{ fontFamily: "Helvetica-Bold", fontSize: 9.5 }}>{clean(t.archetype)}</Text>
                    <Text style={s.body}>{clean(t.rationale)}</Text>
                    <Text style={s.small}>Trade-off: {clean(t.trade_off)}</Text>
                  </View>
                ))}
                <Text style={s.h3}>BUSCAS SUGERIDAS (LINKEDIN RECRUITER)</Text>
                {report.search_plan.boolean_queries.map((q) => (
                  <Text
                    key={q}
                    style={{ fontFamily: "Courier", fontSize: 7.5, backgroundColor: C.wash, padding: 5, marginBottom: 4 }}
                  >
                    {clean(q)}
                  </Text>
                ))}
                <Text style={s.h3}>PERGUNTAS DE TRIAGEM</Text>
                <Bullets items={report.search_plan.screening_questions} mark="#" />
              </View>
            )}
          </View>
        )}

        <View style={[s.section, { borderTopWidth: 0.75, borderTopColor: C.rule, paddingTop: 10 }]} wrap={false}>
          <Text style={s.eyebrow}>Como este parecer foi produzido</Text>
          <Text style={[s.small, { marginTop: 4 }]}>
            Busca semântica e lexical na base de {metadata.candidates_screened} perfis, seguida de avaliação
            individual por modelo de linguagem ({metadata.model}) sobre perfis pseudonimizados: o modelo não
            recebe nomes, contatos nem marcas de gênero. Cada afirmação citada foi conferida literalmente no
            currículo; o que não foi encontrado foi descartado. A nota combina {weights}, com desconto quando
            parte das evidências não é confirmada. Este documento apoia a decisão dos sócios e não a substitui.
          </Text>
        </View>

      </Page>
    </Document>
  );
}
