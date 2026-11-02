import React, { useState } from 'react';
import { Send, CornerDownLeft, Sparkles } from 'lucide-react';

export default function ChatInput({ onSendMessage, disabled = false, isSending = false, placeholder }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || disabled || isSending) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleQuickQuestion = (q) => {
    if (disabled || isSending) return;
    onSendMessage(q);
  };

  return (
    <div className="bg-white border-top p-3 sticky-bottom">
      {/* Quick suggested prompt chips */}
      <div className="d-flex align-items-center gap-2 mb-2 overflow-auto pb-1" style={{ whiteSpace: 'nowrap' }}>
        <span className="text-muted small d-flex align-items-center gap-1" style={{ fontSize: '0.72rem' }}>
          <Sparkles size={12} className="text-warning" /> Suggested:
        </span>
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm py-0 px-2 rounded-pill"
          style={{ fontSize: '0.72rem' }}
          onClick={() => handleQuickQuestion('What is the recommended spindle warmup procedure?')}
          disabled={disabled || isSending}
        >
          Spindle warmup procedure
        </button>
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm py-0 px-2 rounded-pill"
          style={{ fontSize: '0.72rem' }}
          onClick={() => handleQuickQuestion('What pressure threshold triggers emergency shutoff?')}
          disabled={disabled || isSending}
        >
          Emergency pressure cutoff
        </button>
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm py-0 px-2 rounded-pill"
          style={{ fontSize: '0.72rem' }}
          onClick={() => handleQuickQuestion('Can I replace hydraulic fluid with synthetic bio-diesel blend?')}
          disabled={disabled || isSending}
        >
          Bio-diesel hydraulic fluid (Test Insufficient Evidence)
        </button>
      </div>

      <form onSubmit={handleSubmit} className="d-flex gap-2">
        <textarea
          rows={2}
          className="form-control"
          placeholder={placeholder || (disabled ? 'Select a machine first to ask questions...' : 'Ask a technical or maintenance question about this machine... (Press Enter to send)')}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || isSending}
          style={{ resize: 'none', fontSize: '0.9rem' }}
        />
        <button
          type="submit"
          className="btn btn-primary-industrial px-4 d-flex align-items-center justify-content-center gap-2"
          disabled={disabled || isSending || !input.trim()}
          title="Send query"
        >
          {isSending ? (
            <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
          ) : (
            <>
              <Send size={16} />
              <span className="d-none d-md-inline">Send</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
