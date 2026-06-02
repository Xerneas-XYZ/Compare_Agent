"""
Tracing — OpenTelemetry + LangSmith
Initialise once at app startup.
"""
import logging
import os
from app.core.config import settings

logger = logging.getLogger(__name__)


def init_tracer():
    """Configure LangSmith tracing if API key is present."""
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        logger.info(f"LangSmith tracing enabled → project: {settings.LANGCHAIN_PROJECT}")
    else:
        logger.info("LangSmith tracing disabled (no API key)")

    # OpenTelemetry optional instrumentation
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider = TracerProvider()
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry tracer configured")
    except ImportError:
        logger.debug("opentelemetry not installed; skipping OTel setup")