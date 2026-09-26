// Mirrors curator.domain.models (backend). Keep in sync when the API changes.

export type Requirement = { name: string; importance: "essencial" | "desejavel" };

export type JobProfile = {
  role_title: string;
  mandate: string;
  company_context: string;
  hard_requirements: Requirement[];
  soft_requirements: Requirement[];
  search_queries: string[];
};

export type DimensionScore = { score: number; rationale: string };

export type Evidence = {
  requirement: string;
  claim: string;
  quote: string;
  verified: boolean;
  match_score: number;
  start: number | null;
  end: number | null;
};

export type Recommendation = "avancar" | "avancar_com_ressalvas" | "nao_priorizar";

export type RankedCandidate = {
  rank: number;
  candidate_id: string;
  name: string;
  current_role: string;
  final_score: number;
  retrieval_score: number;
  grounding_rate: number;
  scores: Record<"hard_skills" | "soft_skills" | "context_fit", DimensionScore>;
  headline: string;
  analysis: string;
  recommendation: Recommendation;
  evidence: Evidence[];
  gaps: string[];
  interview_focus: string[];
  profile_text: string;
};

export type MatchReport = {
  job: JobProfile;
  executive_summary: string;
  next_steps: string[];
  top_candidates: RankedCandidate[];
  also_considered: { candidate_id: string; name: string; final_score: number; reason: string }[];
  metadata: {
    run_id: string;
    model: string;
    elapsed_ms: number;
    candidates_screened: number;
    pii_redactions: number;
    llm_calls: number;
  };
};

export type StageName = "sanitize" | "analyze_job" | "retrieve" | "assess" | "rank" | "synthesize";

export type StageEvent = {
  type: "stage";
  stage: StageName;
  message: string;
  data: Record<string, unknown>;
};

export type StreamEvent =
  | StageEvent
  | { type: "report"; report: MatchReport }
  | { type: "error"; message: string };

export type CandidateSummary = {
  candidate_id: string;
  name: string;
  current_role: string;
  profile_text: string;
};

export type EvaluationCase = {
  case_id: string;
  title: string;
  expected_top: string;
  predicted_ranking: string[];
  hit_at_1: boolean;
  reciprocal_rank: number;
  grounding_rate: number;
  judge: {
    executive_tone: number;
    decision_usefulness: number;
    factual_consistency: number;
    critique: string;
  } | null;
  report: MatchReport;
};

export type EvaluationReport = {
  generated_at: string;
  model: string;
  summary: {
    cases: number;
    hit_at_1: number;
    mrr: number;
    grounding_rate: number;
    judge_executive_tone: number | null;
    judge_decision_usefulness: number | null;
    judge_factual_consistency: number | null;
  };
  cases: EvaluationCase[];
};
