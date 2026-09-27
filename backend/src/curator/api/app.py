import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from curator import __version__
from curator.agent.graph import CurationError
from curator.agent.llm import LLMError
from curator.api.schemas import (
    CandidateSummary,
    FeedbackRequest,
    HealthResponse,
    MatchRequest,
)
from curator.api.security import RateLimiter, client_key, require_api_key
from curator.config import Settings, get_settings
from curator.domain.models import MatchReport
from curator.logging import configure_logging
from curator.privacy.pseudonymizer import redact
from curator.service import CurationService, build_service

log = structlog.get_logger(__name__)

ServiceFactory = Callable[[Settings], CurationService]


def create_app(
    settings: Settings | None = None, service_factory: ServiceFactory = build_service
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.environment == "production")
    limiter = RateLimiter(settings.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = service_factory(settings)
        log.info("api.ready", candidates=len(app.state.service.repo))
        yield

    is_prod = settings.environment == "production"
    app = FastAPI(
        title="Curator API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    def service(request: Request) -> CurationService:
        return request.app.state.service  # type: ignore[no-any-return]

    ApiKey = Annotated[str, Depends(require_api_key)]

    def rate_limited(request: Request, api_key: ApiKey) -> str:
        limiter.check(client_key(request, api_key))
        return api_key

    Service = Annotated[CurationService, Depends(service)]
    RateLimited = Annotated[str, Depends(rate_limited)]

    @app.get("/health", response_model=HealthResponse)
    def health(svc: Service) -> HealthResponse:
        return HealthResponse(status="ok", candidates=len(svc.repo), model=settings.llm_model)

    @app.get("/v1/candidates", response_model=list[CandidateSummary])
    def list_candidates(svc: Service, _: ApiKey) -> list[CandidateSummary]:
        # Contact data is deliberately not exposed: the UI doesn't need it.
        return [
            CandidateSummary(
                candidate_id=p.candidate_id,
                name=svc.repo.identity(p.candidate_id).name,
                current_role=p.current_role,
                profile_text=p.summary,
            )
            for p in svc.repo.profiles
        ]

    @app.post("/v1/match", response_model=MatchReport)
    async def match(
        body: MatchRequest,
        svc: Service,
        _: RateLimited,
    ) -> MatchReport:
        try:
            return await svc.run(body.job_description, body.weights)
        except LLMError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
        except CurationError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    @app.post("/v1/match/stream")
    async def match_stream(
        body: MatchRequest,
        svc: Service,
        _: RateLimited,
    ) -> EventSourceResponse:
        async def events() -> AsyncIterator[dict[str, str]]:
            try:
                async for event in svc.stream(body.job_description, body.weights):
                    yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
            except (LLMError, CurationError) as exc:
                yield {"event": "error", "data": json.dumps({"type": "error", "message": str(exc)})}
            except Exception:
                log.exception("curation.failed")
                payload = {"type": "error", "message": "internal error, see server logs"}
                yield {"event": "error", "data": json.dumps(payload)}

        return EventSourceResponse(events(), ping=15)

    @app.get("/v1/evaluation")
    def evaluation(_: ApiKey) -> list[Any]:
        """One report per evaluated model, for side-by-side comparison."""
        paths = sorted(settings.eval_reports_dir.glob("evaluation-*.json"))
        return [json.loads(p.read_text(encoding="utf-8")) for p in paths]

    @app.post("/v1/feedback", status_code=status.HTTP_204_NO_CONTENT)
    def feedback(body: FeedbackRequest, _: RateLimited) -> Response:
        record = body.model_dump()
        if record["comment"]:
            record["comment"] = redact(record["comment"]).text
        record["created_at"] = datetime.now(UTC).isoformat()
        settings.feedback_path.parent.mkdir(parents=True, exist_ok=True)
        with settings.feedback_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app
