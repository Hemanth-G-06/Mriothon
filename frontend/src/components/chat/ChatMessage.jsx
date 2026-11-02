import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Bot, User, AlertTriangle, Layers } from 'lucide-react';
import CitationCard from './CitationCard';
import { formatDateTime } from '../../utils/formatters';
import { INSUFFICIENT_EVIDENCE_MESSAGE } from '../../utils/constants';

export default function ChatMessage({ message, machineName, onOpenPdf }) {
  const { question, answer, citations = [], is_insufficient_evidence, created_at, isPending } = message;

  // Detect whether backend indicates insufficient evidence across standard fields
  const isInsufficient = Boolean(
    is_insufficient_evidence === true ||
    message.is_insufficient_evidence === true ||
    message.insufficient_evidence === true ||
    message.status === 'insufficient_evidence' ||
    message.has_sufficient_evidence === false ||
    message.evidence_found === false ||
    (typeof answer === 'string' && (
      answer.toLowerCase().includes("couldn't find sufficient information") ||
      answer.toLowerCase().includes("insufficient evidence")
    ))
  );

  return (
    <div className="mb-4 d-flex flex-column gap-3">
      {/* User Question */}
      <div className="d-flex justify-content-end align-items-start gap-2">
        <div className="chat-bubble-user">
          <div className="d-flex align-items-center justify-content-between gap-3 mb-1">
            <span className="badge bg-white text-dark small" style={{ fontSize: '0.68rem' }}>
              {machineName || 'Machine'}
            </span>
            {created_at && (
              <span className="text-white-50 small" style={{ fontSize: '0.68rem' }}>
                {formatDateTime(created_at)}
              </span>
            )}
          </div>
          <div className="fw-normal" style={{ fontSize: '0.92rem', whiteSpace: 'pre-wrap' }}>
            {question}
          </div>
        </div>
        <div className="p-2 rounded-circle bg-primary text-white flex-shrink-0">
          <User size={16} />
        </div>
      </div>

      {/* Assistant Response */}
      <div className="d-flex justify-content-start align-items-start gap-2">
        <div className="p-2 rounded-circle bg-dark text-white flex-shrink-0">
          <Bot size={16} />
        </div>
        <div className="chat-bubble-assistant">
          <div className="d-flex align-items-center gap-2 mb-2 pb-1 border-bottom">
            <span className="fw-semibold small text-primary">Manual Assistant</span>
            <span className="text-muted small">|</span>
            <span className="text-muted small" style={{ fontSize: '0.72rem' }}>
              Grounding: {machineName || 'Selected Machine'}
            </span>
          </div>

          {isPending ? (
            <div className="d-flex align-items-center gap-2 text-muted py-2">
              <span className="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true" />
              <span className="small">Retrieving relevant manual sections & synthesizing answer...</span>
            </div>
          ) : isInsufficient ? (
            <div className="alert alert-warning border border-warning d-flex align-items-start gap-2 mb-2 py-2">
              <AlertTriangle size={18} className="text-warning flex-shrink-0 mt-1" />
              <div>
                <strong className="d-block small">Insufficient Evidence</strong>
                <span className="small">{INSUFFICIENT_EVIDENCE_MESSAGE}</span>
              </div>
            </div>
          ) : (
            <div className="assistant-markdown-content" style={{ fontSize: '0.92rem', lineHeight: '1.5' }}>
              <ReactMarkdown>{answer}</ReactMarkdown>
            </div>
          )}

          {/* Source Citations (Never rendered for pending or insufficient-evidence responses) */}
          {!isPending && !isInsufficient && citations && citations.length > 0 && (
            <div className="mt-3 pt-2 border-top">
              <div className="d-flex align-items-center gap-1 text-muted small fw-semibold mb-2">
                <Layers size={13} />
                <span>Verified Source Citations ({citations.length}):</span>
              </div>
              <div className="d-flex flex-column gap-1">
                {citations.map((citation, idx) => (
                  <CitationCard
                    key={citation.id || `cit-${idx}`}
                    citation={citation}
                    onOpenPdf={onOpenPdf}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
