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
    skip_judge: Annotated[bool, typer.Option(help="Skip the LLM-as-judge step.")] = False,
) -> None:
    """Run the reference job descriptions and write reports/evaluation.json."""
    from curator.agent.llm import ClaudeClient
    from curator.evaluation.runner import evaluate as run_eval
    from curator.evaluation.runner import load_cases, write_report
    from curator.service import build_service

    s = get_settings()
    service = build_service(s)
    judge = None if skip_judge else ClaudeClient(s)
    result = asyncio.run(run_eval(service, load_cases(s.eval_cases_path), judge))
    write_report(result, s.eval_report_path)

    for case in result["cases"]:
        mark = "OK " if case["hit_at_1"] else "MISS"
        typer.echo(f"[{mark}] {case['title']}: {' > '.join(case['predicted_ranking'])}")
    typer.echo(f"\nsummary: {result['summary']}")
    if result["summary"]["hit_at_1"] < 1:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
