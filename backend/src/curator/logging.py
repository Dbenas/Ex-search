import logging

import structlog

from curator.privacy.log_filter import scrub_pii


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    logging.basicConfig(format="%(message)s", level=level)
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            scrub_pii,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
    )
