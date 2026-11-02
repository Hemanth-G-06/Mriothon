import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { machineService } from '../../services/machineService';
import { chatService } from '../../services/chatService';
import MachineSelector from '../../components/chat/MachineSelector';
import ChatMessage from '../../components/chat/ChatMessage';
import ChatInput from '../../components/chat/ChatInput';
import PdfViewerModal from '../../components/pdf/PdfViewerModal';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import { MessageSquare, AlertCircle, RefreshCw, History, Cpu, Scan, Layers, Sparkles } from 'lucide-react';
import { getErrorMessage } from '../../utils/errorHandler';

export default function EngineerDashboard() {
  const [machines, setMachines] = useState([]);
  const [selectedMachineId, setSelectedMachineId] = useState('');
  const [messages, setMessages] = useState([]);
  const [historyItems, setHistoryItems] = useState([]);
  const [isLoadingMachines, setIsLoadingMachines] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);

  // PDF Viewer Modal State
  const [pdfModal, setPdfModal] = useState({
    isOpen: false,
    documentId: null,
    documentTitle: '',
    revision: '',
    pageNumber: 1,
    directPdfUrl: null
  });

  const chatEndRef = useRef(null);

  // Auto scroll to bottom of chat
  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSending]);

  // Load assigned machines on mount
  useEffect(() => {
    const fetchMachines = async () => {
      setIsLoadingMachines(true);
      setError(null);
      try {
        const list = await machineService.getMachines();
        const validList = Array.isArray(list) ? list : [];
        setMachines(validList);
        if (validList.length > 0) {
          // Pre-select first machine by default
          setSelectedMachineId(String(validList[0].id));
        }
      } catch (err) {
        setError(getErrorMessage(err, 'Unable to connect to the server. Please check your connection and try again.'));
      } finally {
        setIsLoadingMachines(false);
      }
    };

    fetchMachines();
  }, []);

  // When selectedMachineId changes, fetch machine-specific conversation history
  useEffect(() => {
    if (!selectedMachineId) {
      setMessages([]);
      setHistoryItems([]);
      return;
    }

    const fetchHistory = async () => {
      setIsLoadingHistory(true);
      try {
        const history = await chatService.getChatHistory(selectedMachineId);
        setHistoryItems(history);
        setMessages(history);
      } catch (err) {
        console.error('Failed to load machine chat history:', err);
      } finally {
        setIsLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [selectedMachineId]);

  const handleSelectMachine = (newMachineId) => {
    if (newMachineId === selectedMachineId) return;
    setSelectedMachineId(newMachineId);
    setMessages([]);
    setHistoryItems([]);
    setError(null);
  };

  const handleSendMessage = async (questionText) => {
    if (isSending) return;
    if (!selectedMachineId) {
      setError('Please select a machine first.');
      return;
    }

    setError(null);
    setIsSending(true);

    // Optimistically add question with isPending = true
    const pendingMsgId = 'pending-' + Date.now();
    const optimisticMessage = {
      id: pendingMsgId,
      question: questionText,
      answer: '',
      citations: [],
      isPending: true,
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, optimisticMessage]);

    try {
      const response = await chatService.askQuestion(selectedMachineId, questionText);
      // Replace pending message with completed response
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingMsgId ? response : m))
      );
      // Also update history list
      setHistoryItems((prev) => [response, ...prev]);
    } catch (err) {
      // Remove pending message and show error
      setMessages((prev) => prev.filter((m) => m.id !== pendingMsgId));
      setError(getErrorMessage(err, 'Unable to process your question right now. Please try again.'));
    } finally {
      setIsSending(false);
    }
  };

  const handleOpenPdf = ({ document_id, document_title, revision, page_number, pdf_url }) => {
    if (!document_id && !pdf_url) {
      setError('Citation metadata is missing document identifier. Unable to open PDF manual.');
      return;
    }
    setPdfModal({
      isOpen: true,
      documentId: document_id,
      documentTitle: document_title || 'Technical Manual',
      revision: revision || 'Rev 1.0',
      pageNumber: Math.max(1, Number(page_number) || 1),
      directPdfUrl: pdf_url || null
    });
  };

  const handleClosePdf = () => {
    setPdfModal((prev) => ({ ...prev, isOpen: false }));
  };

  const currentMachine = machines.find((m) => String(m.id) === String(selectedMachineId));

  if (isLoadingMachines) {
    return <LoadingSpinner text="Loading assigned machines and technical indexes..." size="lg" />;
  }

  return (
    <div className="d-flex flex-column h-100" style={{ minHeight: 'calc(100vh - 120px)' }}>
      {/* Visual Quality Inspection Quick Navigation Section */}
      <div className="card card-industrial p-3 bg-white mb-3">
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3">
          <div className="d-flex align-items-center gap-3">
            <div className="p-2 rounded bg-primary bg-opacity-10 text-primary">
              <Scan size={22} />
            </div>
            <div>
              <div className="d-flex align-items-center gap-2">
                <h6 className="fw-bold text-dark mb-0">AI Visual Quality Inspection</h6>
                <span className="badge bg-primary text-white" style={{ fontSize: '0.68rem' }}>MODULE B</span>
              </div>
              <p className="text-muted small mb-0" style={{ fontSize: '0.78rem' }}>
                Automated surface defect classification using model <strong>BIT-PLATE-CV-1.0</strong>.
              </p>
            </div>
          </div>
          <div className="d-flex flex-wrap gap-2">
            <Link to="/engineer/quality-inspection" className="btn btn-primary-industrial btn-sm d-flex align-items-center gap-1">
              <Scan size={14} /> Single Inspection
            </Link>
            <Link to="/engineer/batch-inspection" className="btn btn-outline-primary btn-sm d-flex align-items-center gap-1">
              <Layers size={14} /> Batch Inspection
            </Link>
            <Link to="/engineer/inspection-history" className="btn btn-outline-secondary btn-sm d-flex align-items-center gap-1">
              <History size={14} /> Inspection History
            </Link>
          </div>
        </div>
      </div>

      {/* Top Machine Selector Bar */}
      <MachineSelector
        machines={machines}
        selectedMachineId={selectedMachineId}
        onSelectMachine={handleSelectMachine}
        disabled={isSending}
      />

      {/* Error alert */}
      {error && (
        <div className="alert alert-danger py-2 small d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center gap-2">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button className="btn btn-sm btn-link text-danger p-0" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Main Conversation Container */}
      <div className="row g-3 flex-grow-1">
        {/* Left Side: Chat Conversation Area */}
        <div className="col-lg-9 col-12 d-flex flex-column">
          <div
            className="card card-industrial flex-grow-1 d-flex flex-column p-0 bg-white shadow-sm"
            style={{ minHeight: '520px', maxHeight: '72vh' }}
          >
            {/* Chat scrollable body */}
            <div className="card-body p-3 p-md-4 overflow-auto flex-grow-1">
              {!selectedMachineId ? (
                <EmptyState
                  title="No Machine Selected"
                  description="Choose a manufacturing machine from the dropdown above to query its operations and maintenance manuals."
                  icon={Cpu}
                />
              ) : isLoadingHistory ? (
                <LoadingSpinner text="Retrieving previous manual inquiries..." />
              ) : messages.length === 0 ? (
                <EmptyState
                  title={`Ready for questions on ${currentMachine?.name || 'Machine'}`}
                  description="Ask about operating parameters, torque tolerances, fault troubleshooting, or safety procedures directly verified by the uploaded manuals."
                  icon={MessageSquare}
                />
              ) : (
                messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    machineName={currentMachine?.name}
                    onOpenPdf={handleOpenPdf}
                  />
                ))
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Bottom Input Area */}
            <ChatInput
              onSendMessage={handleSendMessage}
              disabled={!selectedMachineId || isSending}
              isSending={isSending}
            />
          </div>
        </div>

        {/* Right Side: Previous Questions Quick Sidebar */}
        <div className="col-lg-3 col-12 d-none d-lg-block">
          <div className="card card-industrial p-3 h-100 bg-white d-flex flex-column shadow-sm" style={{ maxHeight: '72vh' }}>
            <div className="d-flex align-items-center justify-content-between pb-2 mb-2 border-bottom">
              <span className="fw-semibold small text-dark d-flex align-items-center gap-1">
                <History size={14} className="text-secondary" /> Personal Query History
              </span>
              <span className="badge bg-light text-secondary border small">
                {historyItems.length}
              </span>
            </div>

            <div className="overflow-auto flex-grow-1 pe-1">
              {historyItems.length === 0 ? (
                <p className="text-muted small text-center my-4">No prior queries for this machine.</p>
              ) : (
                historyItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-2 mb-2 rounded bg-light border text-start cursor-pointer hover-shadow"
                    style={{ cursor: 'pointer' }}
                  >
                    <div className="fw-medium text-dark text-truncate small" style={{ fontSize: '0.8rem' }}>
                      {item.question}
                    </div>
                    <div className="d-flex align-items-center justify-content-between mt-1">
                      <span
                        className={`badge ${
                          item.is_insufficient_evidence
                            ? 'bg-warning bg-opacity-25 text-warning-emphasis'
                            : 'bg-success bg-opacity-25 text-success-emphasis'
                        }`}
                        style={{ fontSize: '0.65rem' }}
                      >
                        {item.is_insufficient_evidence ? 'No evidence' : 'Answered'}
                      </span>
                      <span className="text-muted" style={{ fontSize: '0.68rem' }}>
                        {item.citations ? `${item.citations.length} cited` : ''}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* PDF Modal Viewer */}
      <PdfViewerModal
        isOpen={pdfModal.isOpen}
        onClose={handleClosePdf}
        documentId={pdfModal.documentId}
        documentTitle={pdfModal.documentTitle}
        revision={pdfModal.revision}
        pageNumber={pdfModal.pageNumber}
        directPdfUrl={pdfModal.directPdfUrl}
      />
    </div>
  );
}
