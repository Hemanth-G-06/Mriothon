"""
OpenTelemetry and Langfuse distributed tracing instrumentation for INDUSTRIA X.
Propagates W3C trace contexts and correlates RAG execution with unique trace IDs.
"""

import logging
import os
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Initialize OpenTelemetry Tracer
_TRACER_INITIALIZED = False


def get_tracer():
    global _TRACER_INITIALIZED
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource

        if not _TRACER_INITIALIZED:
            resource = Resource.create({"service.name": "industria-x-backend", "service.version": "2.4.0"})
            provider = TracerProvider(resource=resource)
            
            otlp_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
            if otlp_endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
                except Exception as e:
                    logger.warning("Could not initialize OTLP gRPC exporter: %s", e)

            trace.set_tracer_provider(provider)
            _TRACER_INITIALIZED = True

        return trace.get_tracer("industriax.rag", "2.4.0")
    except Exception as e:
        logger.debug("OpenTelemetry not fully configured: %s", e)
        return None


def generate_trace_id() -> str:
    """Generates a 32-character hexadecimal trace ID."""
    return uuid.uuid4().hex


class LangfuseObserver:
    """
    Lightweight facade for Langfuse observability.
    Logs execution traces if Langfuse credentials exist; otherwise degrades silently.
    """

    def __init__(self):
        self.public_key = os.getenv('LANGFUSE_PUBLIC_KEY', '').strip()
        self.secret_key = os.getenv('LANGFUSE_SECRET_KEY', '').strip()
        self.host = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com').strip()
        self._client = None

        if self.public_key and self.secret_key:
            try:
                from langfuse import Langfuse
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host
                )
            except Exception as e:
                logger.warning("Langfuse client initialization failed: %s", e)

    def log_agent_execution(
        self,
        trace_id: str,
        name: str,
        machine_code: str,
        input_data: Any,
        output_data: Any,
        metadata: Optional[Dict] = None
    ):
        if not self._client:
            return

        try:
            self._client.trace(
                id=trace_id,
                name=name,
                user_id=metadata.get('user_email') if metadata else None,
                input=input_data,
                output=output_data,
                metadata={
                    'machine_code': machine_code,
                    **(metadata or {})
                }
            )
        except Exception as e:
            logger.debug("Langfuse telemetry logging skipped: %s", e)
