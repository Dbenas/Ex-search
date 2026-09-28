import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer

from curator.config import get_settings
from curator.logging import configure_logging

app = typer.Typer(help="Executive talent curation agent.", no_args_is_help=True)


@app.callback()
def _setup() -> None:
    # Windows consoles default to cp1252; the reports are in Portuguese.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    configure_logging(get_settings().log_level)


@app.command()
def ingest() -> None:
    """Index the candidate base into the vector store (idempotent)."""
    from curator.ingestion.loader import CandidateRepository
    from curator.ingestion.pipeline import ingest as run_ingest
    from curator.retrieval.embeddings import Embedder
    from curator.retrieval.vector_store import VectorStore

    s = get_settings()
    report = run_ingest(
        CandidateRepository.from_directory(s.candidates_dir),
        VectorStore(s.chroma_dir, s.collection_name, s.embedding_model),
        Embedder(s.embedding_model, s.embedding_cache_dir),
    )
    typer.echo(
        f"{report.candidates} candidates, {report.chunks} chunks, {report.embedded} embedded"
    )


@app.command()
def match(
    job_file: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Run the curation agent for a job description stored in a text file."""
    from curator.service import build_service

    service = build_service(get_settings())
    report = asyncio.run(service.run(job_file.read_text(encoding="utf-8")))
    typer.echo(f"\n{report.job.role_title}\n{report.executive_summary}\n")
    for c in report.top_candidates:
        typer.echo(f"{c.rank}. {c.name} — {c.final_score} ({c.recommendation})")
        typer.echo(f"   {c.headline}\n   {c.analysis}\n")


@app.command()
def evaluate(
    provider: Annotated[
        str | None, typer.Option(help="anthropic or gemini (defaults to LLM_PROVIDER).")
    ] = None,
    skip_judge: Annotated[bool, typer.Option(help="Skip the LLM-as-judge step.")] = False,
) -> None:
    """Run the reference job descriptions and write reports/evaluation-<model>.json.

    The judge is always Claude, so reports from different providers are comparable.
    """
    from curator.agent.llm import ClaudeClient, build_llm
    from curator.evaluation.runner import evaluate as run_eval
    from curator.evaluation.runner import load_cases, write_report
    from curator.service import build_service

    s = get_settings()
    service = build_service(s, llm=build_llm(s, provider))
    judge = None if skip_judge else ClaudeClient(s)
    result = asyncio.run(run_eval(service, load_cases(s.eval_cases_path), judge))
    write_report(result, s.eval_reports_dir / f"evaluation-{service.model}.json")

    for case in result["cases"]:
        mark = "OK " if case["hit_at_1"] else "MISS"
        typer.echo(f"[{mark}] {case['title']}: {' > '.join(case['predicted_ranking'])}")
    typer.echo(f"\nsummary: {result['summary']}")
    if result["summary"]["hit_at_1"] < 1:
        raise typer.Exit(code=1)


@app.command("retrieval-eval")
def retrieval_eval() -> None:
    """Search quality before the LLM, with look-alike distractors. No LLM calls."""
    from curator.evaluation.retrieval import evaluate_retrieval
    from curator.evaluation.runner import write_report
    from curator.retrieval.embeddings import Embedder

    s = get_settings()
    result = evaluate_retrieval(
        s.candidates_dir,
        s.eval_cases_path.parent / "retrieval.yaml",
        Embedder(s.embedding_model, s.embedding_cache_dir),
    )
    write_report(result, s.eval_reports_dir / "retrieval.json")
    typer.echo(f"{result['profiles_indexed']} perfis indexados, {result['queries']} consultas\n")
    typer.echo(f"{'método':<10}{'acerto@1':>10}{'recall@3':>10}{'MRR':>8}")
    for mode, m in result["summary"].items():
        typer.echo(f"{mode:<10}{m['hit_at_1']:>10.2f}{m['recall_at_3']:>10.2f}{m['mrr']:>8.3f}")


@app.command("bias-audit")
def bias_audit(
    empirical: Annotated[
        bool,
        typer.Option(
            help="Also measure, with the LLM and without neutralisation, how much the cues "
            "would move scores. Costs credits; asks for confirmation."
        ),
    ] = False,
    repeats: Annotated[int, typer.Option(min=2, max=10)] = 3,
    case: Annotated[str, typer.Option(help="Job used for the empirical test.")] = "vaga-1-cto",
    yes: Annotated[bool, typer.Option("--yes", help="Skip the cost confirmation.")] = False,
) -> None:
    """Check that names cannot influence scores and whether gender still leaks.

    Without --empirical nothing is sent to the LLM and nothing is spent.
    """
    from curator.agent import prompts
    from curator.agent.graph import default_weights
    from curator.agent.llm import build_llm
    from curator.domain.models import JobProfile
    from curator.evaluation.bias import (
        counterfactual_gender,
        estimate_calls,
        gender_invariance,
        gender_leakage,
        name_invariance,
    )
    from curator.evaluation.runner import load_cases, write_report
    from curator.ingestion.loader import CandidateRepository, load_raw_candidates

    s = get_settings()
    raw = load_raw_candidates(s.candidates_dir)
    repo = CandidateRepository(raw)
    # The structural check compares prompts, so any mandate works.
    placeholder = JobProfile(
        role_title="-",
        mandate="-",
        company_context="-",
        hard_requirements=[],
        soft_requirements=[],
        search_queries=[],
    )
    invariance = name_invariance(raw, placeholder, s)
    gender = gender_invariance(repo, placeholder, s)
    leakage = gender_leakage(repo)

    def line(ok: bool, text: str) -> None:
        typer.echo(f"[{'OK' if ok else 'FALHOU'}] {text}")

    line(invariance["passed"], "Troca de nome e contato não altera o texto enviado ao modelo")
    for c in invariance["checks"]:
        typer.echo(f"      {c['original_name']} -> {c['swapped_name']}: {c['identical_prompt']}")
    line(gender["passed"], "Marcas de gênero no CV não alteram o texto enviado ao modelo")
    for c in gender["checks"] or [{"alias": "-", "terms": ["nenhuma marca encontrada"]}]:
        status = "neutralizada" if c.get("identical_prompt") else "CHEGA AO MODELO"
        typer.echo(f"      {c['alias']}: {', '.join(c['terms'])} ({status})")

    report: dict[str, object] = {"name_invariance": invariance, "gender_invariance": gender}

    if empirical and leakage:
        llm = build_llm(s)
        calls = estimate_calls(repo, repeats)
        in_price, out_price = s.model_prices.get(llm.model, (0.0, 0.0))
        # Typical assessment call: ~2.7k input and ~1.3k output tokens.
        cost = calls * (2_700 * in_price + 1_300 * out_price) / 1_000_000
        typer.echo(
            f"\nTeste contrafactual: {calls} chamadas a {llm.model}, cerca de US$ {cost:.2f}."
        )
        if not yes and not typer.confirm("Continuar?"):
            raise typer.Exit()
        job_case = next(c for c in load_cases(s.eval_cases_path) if c["id"] == case)

        async def run() -> list[dict[str, object]]:
            job = await llm.generate(
                system=prompts.HOUSE_STYLE,
                prompt=prompts.JOB_ANALYSIS.format(job_description=job_case["description"]),
                schema=JobProfile,
                task="job_analysis",
            )
            return await counterfactual_gender(llm, repo, job, repeats, default_weights(s))

        results = asyncio.run(run())
        report["counterfactual"] = {"case": case, "repeats": repeats, "results": results}
        for r in results:
            typer.echo(
                f"      {r['alias']}: como está {r['scores_as_is']} | sem marcas "
                f"{r['scores_neutral']} | delta {r['mean_delta']} (ruído ±{r['run_to_run_sd']})"
                f"\n      -> {r['verdict']}"
            )

    write_report(report, s.eval_reports_dir / "bias-audit.json")
    typer.echo(f"\nrelatório: {s.eval_reports_dir / 'bias-audit.json'}")
    if not (invariance["passed"] and gender["passed"]):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
