import logging
import structlog

logging.basicConfig(
    format="%(message)s",
    level=logging.INFO
)

structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()