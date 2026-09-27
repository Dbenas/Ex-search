import type { CandidateScores, ScoreWeights } from "./types";

// Mirrors weighted_score() in backend/src/curator/agent/graph.py. The backend
// stays the source of truth; this only powers the what-if simulation.
export function weightedScore(c: CandidateScores, w: ScoreWeights): number {
  const total = w.hard_skills + w.soft_skills + w.context_fit || 1;
  const base =
    ((w.hard_skills * c.scores.hard_skills +
      w.soft_skills * c.scores.soft_skills +
      w.context_fit * c.scores.context_fit) /
      total) *
    10;
  return Math.round(base * (0.75 + 0.25 * c.grounding_rate) * 10) / 10;
}

export function rerank(candidates: CandidateScores[], w: ScoreWeights) {
  return candidates
    .map((c) => ({ ...c, simulated: weightedScore(c, w) }))
    .sort((a, b) => b.simulated - a.simulated || b.retrieval_score - a.retrieval_score);
}

/**
 * Share of all weight combinations (5% grid over the simplex) in which each
 * candidate ranks first. A leader that wins almost everywhere is a robust call;
 * one that wins only under the default weights is a judgement the partner owns.
 */
export function leadershipShare(candidates: CandidateScores[], step = 0.05): Map<string, number> {
  const wins = new Map<string, number>();
  let combinations = 0;
  const n = Math.round(1 / step);
  for (let i = 0; i <= n; i++) {
    for (let j = 0; j <= n - i; j++) {
      const w = { hard_skills: i / n, soft_skills: j / n, context_fit: (n - i - j) / n };
      const leader = rerank(candidates, w)[0];
      if (leader) wins.set(leader.candidate_id, (wins.get(leader.candidate_id) ?? 0) + 1);
      combinations++;
    }
  }
  return new Map([...wins].map(([id, count]) => [id, count / combinations]));
}
