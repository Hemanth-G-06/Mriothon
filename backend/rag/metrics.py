"""
Prometheus Metrics Instrumentation for INDUSTRIA X.
Exports custom domain metrics for industrial RAG, AgentOps, evidence gating,
machine isolation security, and supervisor workflows.
"""

from prometheus_client import Counter, Histogram, Gauge

# Total assistant requests by machine and evidence outcome
RAG_REQUESTS_TOTAL = Counter(
    'industriax_rag_requests_total',
    'Total technical troubleshooting inquiries processed',
    ['machine_code', 'outcome']
)

# Evidence gate evaluation breakdown
EVIDENCE_GATE_TOTAL = Counter(
    'industriax_evidence_gate_evaluations_total',
    'Total evidence gate outcomes (PASS, PARTIAL, FAIL)',
    ['decision']
)

# Citation verification failures
CITATION_FAILURES_TOTAL = Counter(
    'industriax_citation_failures_total',
    'Total citation grounding verification failures'
)

# Security: Cross-machine access and isolation rejections
CROSS_MACHINE_BLOCKS_TOTAL = Counter(
    'industriax_cross_machine_blocks_total',
    'Total unauthorized cross-machine document retrieval attempts blocked',
    ['machine_code']
)

# Unsupported questions rejected by evidence gate
UNSUPPORTED_QUESTIONS_TOTAL = Counter(
    'industriax_unsupported_questions_total',
    'Total technical questions safely rejected due to missing documentation'
)

# Supervisor escalations generated
ESCALATIONS_TOTAL = Counter(
    'industriax_escalations_total',
    'Total inquiries escalated for human supervisor review',
    ['reason_category']
)

# Work order reviews by supervisor
WORK_ORDER_REVIEWS_TOTAL = Counter(
    'industriax_work_order_reviews_total',
    'Total maintenance work orders reviewed by supervisor',
    ['action']  # approved, rejected
)

# Execution phase latencies
RAG_PHASE_DURATION_SECONDS = Histogram(
    'industriax_rag_phase_duration_seconds',
    'Duration of RAG and agentic execution phases in seconds',
    ['phase'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Document processing lifecycle failures
DOCUMENT_PROCESSING_FAILURES = Counter(
    'industriax_document_processing_failures_total',
    'Total document ingestion and vectorization failures'
)
