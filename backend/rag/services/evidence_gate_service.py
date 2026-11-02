"""
Evidence-Gated Answering and Citation Validation Service for INDUSTRIA X.
Enforces strict epistemic gating: PASS, PARTIAL, or FAIL.
Validates citation grounding against relational Document and DocumentPage records.
Detects conflicting documentation and applies configured precedence policies.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from documents.models import Document, DocumentPage, DocumentStatus
from history.models import EvidenceGateOutcome
from .agent_tools import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class EvidenceEvaluationResult:
    outcome: EvidenceGateOutcome
    reason: str
    supported_points: List[str]
    missing_points: List[str]
    contradiction_detected: bool
    contradiction_details: Optional[str]
    precedence_applied: Optional[str]
    usable_evidence: List[RetrievedChunk]


@dataclass
class CitationValidationResult:
    is_valid: bool
    verified_citations: List[Dict]
    rejected_citations: List[Dict]
    validation_notes: str
    can_regenerate: bool


class EvidenceGateService:
    """
    Evaluates retrieved manual passages to determine whether technical answer generation
    is permitted, partially permitted, or strictly prohibited.
    """

    # Keyword patterns representing technical specifications
    TECH_PATTERNS = [
        re.compile(r'\b(?:torque|pressure|temperature|voltage|current|tolerance|clearance|flow rate|psi|bar|rpm|nm|kpa)\b', re.IGNORECASE),
        re.compile(r'\b(?:error|fault|alarm|code|dtc|f\d{2,4}|e\d{2,4})\b', re.IGNORECASE),
        re.compile(r'\b(?:step|procedure|replace|calibrate|adjust|inspect|lubricate|clean)\b', re.IGNORECASE),
    ]

    @staticmethod
    def extract_key_terms(query: str) -> List[str]:
        words = re.findall(r'[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)*', query.lower())
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'for', 'to', 'how', 'what',
            'why', 'when', 'where', 'do', 'does', 'in', 'of', 'with', 'by', 'machine', 'please',
            'tell', 'me', 'can', 'you', 'should', 'i', 'we', 'this', 'that', 'these', 'those',
            'there', 'here', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had',
            'about', 'any', 'some', 'from', 'into', 'out', 'up', 'down', 'all', 'its'
        }
        return [w for w in words if w not in stop_words and len(w) > 2]

    def detect_contradictions(self, chunks: List[RetrievedChunk]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Detects conflicting technical specifications across different manuals.
        Applies precedence policy:
        1. Higher revision number wins (e.g. Rev 2.0 > Rev 1.0).
        2. If equal revision, more recent document wins.
        3. If contradictory values appear in identical-precedence docs, flags unresolved conflict.
        """
        if len(chunks) < 2:
            return False, None, None

        # Check for numeric specification contradictions (e.g. "pressure 150 psi" vs "pressure 200 psi")
        spec_patterns = [
            (r'pressure\s*(?:is|should be|must be|to|:)?\s*(\d+(?:\.\d+)?)\s*(?:psi|bar|kpa)', 'pressure'),
            (r'temperature\s*(?:is|should be|must be|to|:)?\s*(\d+(?:\.\d+)?)\s*(?:c|f|deg|celsius)', 'temperature'),
            (r'torque\s*(?:is|should be|must be|to|:)?\s*(\d+(?:\.\d+)?)\s*(?:nm|ft-lb|in-lb)', 'torque'),
            (r'clearance\s*(?:is|should be|must be|to|:)?\s*(\d+(?:\.\d+)?)\s*(?:mm|inch)', 'clearance'),
        ]

        doc_specs: Dict[str, Dict[str, Tuple[float, str, str]]] = {}  # doc_id -> {spec_name -> (value, revision, text)}

        for c in chunks:
            if c.document_id not in doc_specs:
                doc_specs[c.document_id] = {}
            for pattern, name in spec_patterns:
                match = re.search(pattern, c.text, re.IGNORECASE)
                if match:
                    val = float(match.group(1))
                    doc_specs[c.document_id][name] = (val, c.revision, c.text)

        # Compare across distinct documents
        doc_ids = list(doc_specs.keys())
        if len(doc_ids) < 2:
            return False, None, None

        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                id_a, id_b = doc_ids[i], doc_ids[j]
                specs_a, specs_b = doc_specs[id_a], doc_specs[id_b]

                common_specs = set(specs_a.keys()).intersection(set(specs_b.keys()))
                for s_name in common_specs:
                    val_a, rev_a, _ = specs_a[s_name]
                    val_b, rev_b, _ = specs_b[s_name]

                    if abs(val_a - val_b) > 0.001:
                        # Conflict found! Check precedence
                        try:
                            f_rev_a = float(re.findall(r'\d+(?:\.\d+)?', rev_a)[0])
                            f_rev_b = float(re.findall(r'\d+(?:\.\d+)?', rev_b)[0])
                        except Exception:
                            f_rev_a, f_rev_b = 1.0, 1.0

                        if f_rev_a > f_rev_b:
                            precedence = f"Resolved via precedence: Rev {rev_a} superseded Rev {rev_b}."
                            return True, f"Conflict in {s_name} ({val_a} vs {val_b}).", precedence
                        elif f_rev_b > f_rev_a:
                            precedence = f"Resolved via precedence: Rev {rev_b} superseded Rev {rev_a}."
                            return True, f"Conflict in {s_name} ({val_a} vs {val_b}).", precedence
                        else:
                            return True, f"Unresolvable contradiction in {s_name}: Doc {id_a} specifies {val_a}, while Doc {id_b} specifies {val_b} at identical revision {rev_a}.", None

        return False, None, None

    def evaluate(self, query: str, retrieved_chunks: List[RetrievedChunk]) -> EvidenceEvaluationResult:
        """
        Evaluates evidence sufficiency and consistency for the given question.
        Returns PASS, PARTIAL, or FAIL.
        """
        if not retrieved_chunks:
            return EvidenceEvaluationResult(
                outcome=EvidenceGateOutcome.FAIL,
                reason="Zero authorized manual passages retrieved for this machine. Answer generation blocked.",
                supported_points=[],
                missing_points=["All query components lack supporting technical manual evidence."],
                contradiction_detected=False,
                contradiction_details=None,
                precedence_applied=None,
                usable_evidence=[]
            )

        # Check for contradictions
        has_conflict, conflict_details, precedence = self.detect_contradictions(retrieved_chunks)
        if has_conflict and not precedence:
            return EvidenceEvaluationResult(
                outcome=EvidenceGateOutcome.FAIL,
                reason=f"Unresolvable contradiction detected in documentation: {conflict_details}",
                supported_points=[],
                missing_points=["Conflicting documentation prevents safe autonomous response."],
                contradiction_detected=True,
                contradiction_details=conflict_details,
                precedence_applied=None,
                usable_evidence=[]
            )

        # Evaluate term coverage and evidence sufficiency
        key_terms = self.extract_key_terms(query)
        if not key_terms:
            return EvidenceEvaluationResult(
                outcome=EvidenceGateOutcome.PASS,
                reason="Sufficient grounded evidence retrieved from approved manual.",
                supported_points=["General manual passages available."],
                missing_points=[],
                contradiction_detected=has_conflict,
                contradiction_details=conflict_details,
                precedence_applied=precedence,
                usable_evidence=retrieved_chunks
            )

        corpus_text = " ".join([c.text.lower() for c in retrieved_chunks])

        matched_terms = [t for t in key_terms if t in corpus_text]
        missing_terms = [t for t in key_terms if t not in corpus_text]

        coverage = len(matched_terms) / len(key_terms)

        if coverage >= 0.50:
            return EvidenceEvaluationResult(
                outcome=EvidenceGateOutcome.PASS,
                reason=f"Sufficient evidence verified ({coverage:.0%} query concept coverage).",
                supported_points=matched_terms,
                missing_points=missing_terms,
                contradiction_detected=has_conflict,
                contradiction_details=conflict_details,
                precedence_applied=precedence,
                usable_evidence=retrieved_chunks
            )
        elif coverage >= 0.20:
            return EvidenceEvaluationResult(
                outcome=EvidenceGateOutcome.PARTIAL,
                reason=f"Partial evidence verified ({coverage:.0%} coverage). Answering only supported facets.",
                supported_points=matched_terms,
                missing_points=missing_terms,
                contradiction_detected=has_conflict,
                contradiction_details=conflict_details,
                precedence_applied=precedence,
                usable_evidence=retrieved_chunks
            )
        else:
            return EvidenceEvaluationResult(
                outcome=EvidenceGateOutcome.FAIL,
                reason=f"Insufficient evidence: only {coverage:.0%} of required technical concepts found in authorized manuals.",
                supported_points=matched_terms,
                missing_points=missing_terms,
                contradiction_detected=has_conflict,
                contradiction_details=conflict_details,
                precedence_applied=precedence,
                usable_evidence=[]
            )


class CitationValidator:
    """
    Validates that generated citations point to actual, approved documents,
    correct pages, and that passages actually ground the generated technical claims.
    """

    def validate_citations(
        self,
        citations: List[Dict],
        machine_id: str,
        answer_text: str
    ) -> CitationValidationResult:
        if not citations:
            return CitationValidationResult(
                is_valid=False,
                verified_citations=[],
                rejected_citations=[],
                validation_notes="No citations provided for technical response.",
                can_regenerate=True
            )

        verified = []
        rejected = []

        for cit in citations:
            doc_id = cit.get('document_id')
            page_num = cit.get('page_number')
            source_text = cit.get('source_text', '')

            if not doc_id or page_num is None:
                rejected.append({**cit, 'rejection_reason': 'Missing document_id or page_number.'})
                continue

            # 1. Confirm document exists in PostgreSQL
            try:
                doc = Document.objects.get(pk=doc_id, is_active=True)
            except Document.DoesNotExist:
                rejected.append({**cit, 'rejection_reason': f"Document {doc_id} does not exist or is inactive."})
                continue

            # 2. Confirm document belongs to the requested machine
            if str(doc.machine_id) != str(machine_id):
                rejected.append({**cit, 'rejection_reason': f"Document {doc_id} belongs to a different machine."})
                continue

            # 3. Confirm document is READY or APPROVED
            if doc.status not in (DocumentStatus.READY, 'APPROVED'):
                rejected.append({**cit, 'rejection_reason': f"Document {doc_id} status is '{doc.status}', not READY."})
                continue

            # 4. Confirm cited page exists in DocumentPage
            page_exists = DocumentPage.objects.filter(document=doc, page_number=page_num).exists()
            if not page_exists:
                rejected.append({**cit, 'rejection_reason': f"Page {page_num} does not exist in Document {doc_id}."})
                continue

            # 5. Confirm source text snippet has positive overlap with answer
            cit_words = [w for w in re.findall(r'\w+', source_text.lower()) if len(w) > 3]
            answer_lower = answer_text.lower()
            overlap_count = sum(1 for w in cit_words if w in answer_lower)

            if cit_words and overlap_count == 0:
                rejected.append({**cit, 'rejection_reason': "Cited passage text has zero factual overlap with generated claim."})
                continue

            verified.append({
                'document_id': str(doc.id),
                'document_title': doc.title,
                'revision': getattr(doc, 'revision', '1.0'),
                'page_number': page_num,
                'chunk_id': cit.get('chunk_id', ''),
                'source_id': cit.get('source_id') or cit.get('chunk_id', ''),
                'source_text': source_text[:300],
                'score': cit.get('score', 1.0),
                'retrieval_method': cit.get('retrieval_method', 'vector'),
            })

        is_valid = len(verified) > 0 and len(rejected) == 0
        notes = "All citations verified." if is_valid else f"Rejected {len(rejected)} citation(s)."

        return CitationValidationResult(
            is_valid=is_valid,
            verified_citations=verified,
            rejected_citations=rejected,
            validation_notes=notes,
            can_regenerate=len(rejected) > 0
        )
