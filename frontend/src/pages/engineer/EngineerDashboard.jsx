import React, { useState, useEffect, useRef } from 'react';
import { machineService } from '../../services/machineService';
import { chatService } from '../../services/chatService';
import MachineSelector from '../../components/chat/MachineSelector';
import ChatMessage from '../../components/chat/ChatMessage';
import ChatInput from '../../components/chat/ChatInput';
import PdfViewerModal from '../../components/pdf/PdfViewerModal';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';
import {
  MessageSquare,
  AlertCircle,
  Plus,
  Trash2,
  Cpu,
  History,
  Menu,
  X,
  Layers,
  Clock,
  ChevronRight,
  Bot
} from 'lucide-react';
import { getErrorMessage } from '../../utils/errorHandler';
import { formatDateTime } from '../../utils/formatters';

export default function EngineerDashboard() {
  const [machines, setMachines] = useState([]);
  const [selectedMachineId, setSelectedMachineId] = useState('');
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);

  const [isLoadingMachines, setIsLoadingMachines] = useState(true);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);

  // Mobile drawer toggle
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Delete Conversation Modal State
  const [deleteModal, setDeleteModal] = useState({
    isOpen: false,
    conversationId: null,
    title: '',
    isDeleting: false
  });

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

  // Load conversations on mount
  const loadConversations = async (autoSelectFirst = true) => {
    setIsLoadingConversations(true);
    try {
      const list = await chatService.getConversations();
      const validList = Array.isArray(list) ? list : [];
      setConversations(validList);

      if (autoSelectFirst && validList.length > 0 && !activeConversationId) {
        loadConversation(validList[0].id);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  };

  useEffect(() => {
    loadConversations(true);
  }, []);

  // Load a single conversation and its messages
  const loadConversation = async (conversationId) => {
    if (!conversationId) return;
    setIsLoadingMessages(true);
    setError(null);
    try {
      const conv = await chatService.getConversation(conversationId);
      setActiveConversationId(conv.id);
      setMessages(Array.isArray(conv.messages) ? conv.messages : []);
      // Restore the conversation's grounded machine context
      if (conv.machine_id) {
        setSelectedMachineId(String(conv.machine_id));
      }
      setIsMobileSidebarOpen(false);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load conversation history.'));
    } finally {
      setIsLoadingMessages(false);
    }
  };

  // Start a new chat session
  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    setIsMobileSidebarOpen(false);
  };

  // Switch machine selector
  const handleSelectMachine = (newMachineId) => {
    if (newMachineId === selectedMachineId) return;
    setSelectedMachineId(newMachineId);

    // If currently viewing a conversation for a different machine, switch to New Chat
    const currentConv = conversations.find((c) => String(c.id) === String(activeConversationId));
    if (currentConv && String(currentConv.machine_id) !== String(newMachineId)) {
      setActiveConversationId(null);
      setMessages([]);
    }
    setError(null);
  };

  // Send a user question
  const handleSendMessage = async (questionText) => {
    if (isSending) return;
    if (!selectedMachineId) {
      setError('Please select an authorized machine first.');
      return;
    }

    setError(null);
    setIsSending(true);

    let targetConvId = activeConversationId;

    // Optimistically add the user question to the message list
    const pendingUserMsgId = 'opt-user-' + Date.now();
    const optimisticUserMsg = {
      id: pendingUserMsgId,
      role: 'USER',
      content: questionText,
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, optimisticUserMsg]);

    try {
      // 1. If starting a New Chat, create the persistent conversation record first
      if (!targetConvId) {
        const titleSnippet = questionText.length > 50 ? `${questionText.slice(0, 50)}...` : questionText;
        const newConv = await chatService.createConversation(selectedMachineId, titleSnippet);
        targetConvId = newConv.id;
        setActiveConversationId(newConv.id);
        // Prepend to conversations list
        setConversations((prev) => [newConv, ...prev]);
      }

      // 2. Submit the message to the conversation
      const response = await chatService.sendMessage(targetConvId, questionText);

      // 3. Update the messages list: replace optimistic user message and append assistant message
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== pendingUserMsgId);
        const userMsg = response.user_message || optimisticUserMsg;
        const asstMsg = response.assistant_message || {
          id: 'asst-' + Date.now(),
          role: 'ASSISTANT',
          content: response.answer,
          citations: response.citations || [],
          created_at: new Date().toISOString()
        };
        return [...filtered, userMsg, asstMsg];
      });

      // 4. Refresh conversation list ordering
      loadConversations(false);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to process message with manual assistant.'));
    } finally {
      setIsSending(false);
    }
  };

  // Trigger Delete Confirmation Modal
  const handlePromptDelete = (e, conv) => {
    e.stopPropagation();
    setDeleteModal({
      isOpen: true,
      conversationId: conv.id,
      title: conv.title,
      isDeleting: false
    });
  };

  // Confirm permanent conversation deletion
  const handleConfirmDelete = async () => {
    if (!deleteModal.conversationId || deleteModal.isDeleting) return;
    setDeleteModal((prev) => ({ ...prev, isDeleting: true }));
    try {
      await chatService.deleteConversation(deleteModal.conversationId);
      setConversations((prev) => prev.filter((c) => c.id !== deleteModal.conversationId));

      // If the deleted conversation was active, switch to New Chat
      if (activeConversationId === deleteModal.conversationId) {
        handleNewChat();
      }
      setDeleteModal({ isOpen: false, conversationId: null, title: '', isDeleting: false });
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete conversation.'));
      setDeleteModal((prev) => ({ ...prev, isDeleting: false }));
    }
  };

  // Open PDF Modal
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

  const currentMachine = machines.find((m) => String(m.id) === String(selectedMachineId));
  const activeConversation = conversations.find((c) => c.id === activeConversationId);

  if (isLoadingMachines) {
    return <LoadingSpinner text="Loading authorized machines and manual indexes..." size="lg" />;
  }

  return (
    <div className="d-flex flex-column h-100" style={{ minHeight: 'calc(100vh - 120px)' }}>
      {/* Top Bar: Machine Selector & Mobile History Toggle */}
      <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <div className="d-flex align-items-center gap-2">
          {/* Mobile history toggle button */}
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm d-lg-none d-flex align-items-center gap-1"
            onClick={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
            title="Toggle Conversations History"
          >
            <History size={16} />
            <span>Chats ({conversations.length})</span>
          </button>

          <MachineSelector
            machines={machines}
            selectedMachineId={selectedMachineId}
            onSelectMachine={handleSelectMachine}
            disabled={isSending}
          />
        </div>

        {activeConversation && (
          <div className="d-flex align-items-center gap-2 small text-muted">
            <span className="badge bg-light text-dark border">
              Grounded: {activeConversation.machine_code || currentMachine?.machine_code || 'OEM'}
            </span>
            <span className="text-truncate d-none d-md-inline" style={{ maxWidth: '280px' }}>
              {activeConversation.title}
            </span>
          </div>
        )}
      </div>

      {/* Error alert banner */}
      {error && (
        <div className="alert alert-danger py-2 small d-flex align-items-center justify-content-between mb-3 shadow-sm">
          <div className="d-flex align-items-center gap-2">
            <AlertCircle size={16} className="text-danger flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button className="btn btn-sm btn-link text-danger p-0" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Main Two-Panel ChatGPT-Style Container */}
      <div className="row g-3 flex-grow-1 position-relative">
        {/* =========================================================================
            LEFT PANEL: Conversation History Sidebar
            ========================================================================= */}
        <div
          className={`col-lg-3 col-12 d-lg-block ${
            isMobileSidebarOpen ? 'd-block position-fixed start-0 top-0 h-100 bg-white shadow-lg p-3' : 'd-none'
          }`}
          style={isMobileSidebarOpen ? { zIndex: 1050, width: '320px', maxWidth: '85vw' } : {}}
        >
          <div className="card card-industrial p-3 h-100 bg-white d-flex flex-column shadow-sm" style={{ maxHeight: '72vh' }}>
            {/* Header: New Chat Button & Close on mobile */}
            <div className="d-flex align-items-center justify-content-between gap-2 mb-3">
              <button
                type="button"
                className="btn btn-primary-industrial btn-sm w-100 d-flex align-items-center justify-content-center gap-2 py-2 fw-medium shadow-sm"
                onClick={handleNewChat}
                disabled={isSending}
              >
                <Plus size={16} />
                <span>New Chat</span>
              </button>

              {isMobileSidebarOpen && (
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary d-lg-none"
                  onClick={() => setIsMobileSidebarOpen(false)}
                >
                  <X size={16} />
                </button>
              )}
            </div>

            {/* Conversation History List Header */}
            <div className="d-flex align-items-center justify-content-between pb-2 mb-2 border-bottom">
              <span className="fw-semibold small text-muted text-uppercase" style={{ fontSize: '0.72rem', letterSpacing: '0.5px' }}>
                Chat History ({conversations.length})
              </span>
            </div>

            {/* Scrollable Conversation List */}
            <div className="overflow-auto flex-grow-1 pe-1">
              {isLoadingConversations ? (
                <div className="py-4 text-center">
                  <span className="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true" />
                  <p className="text-muted small mt-2">Loading chats...</p>
                </div>
              ) : conversations.length === 0 ? (
                <div className="text-center py-4 px-2">
                  <MessageSquare size={24} className="text-muted mb-2 opacity-50" />
                  <p className="text-muted small mb-0">No prior chats.</p>
                  <p className="text-muted" style={{ fontSize: '0.72rem' }}>
                    Click <strong>New Chat</strong> to ask about {currentMachine?.name || 'this machine'}.
                  </p>
                </div>
              ) : (
                conversations.map((conv) => {
                  const isActive = conv.id === activeConversationId;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => loadConversation(conv.id)}
                      className={`p-2 mb-2 rounded border text-start cursor-pointer transition-all d-flex align-items-start justify-content-between gap-2 ${
                        isActive
                          ? 'bg-primary bg-opacity-10 border-primary text-primary shadow-sm'
                          : 'bg-light bg-opacity-50 border-light-subtle text-dark hover-shadow'
                      }`}
                      style={{ cursor: 'pointer' }}
                    >
                      <div className="overflow-hidden flex-grow-1">
                        <div className="d-flex align-items-center gap-1 mb-1">
                          <span
                            className="badge bg-secondary bg-opacity-10 text-secondary border font-monospace"
                            style={{ fontSize: '0.65rem' }}
                          >
                            {conv.machine_code || 'OEM'}
                          </span>
                          <span className="text-muted" style={{ fontSize: '0.65rem' }}>
                            {conv.updated_at ? formatDateTime(conv.updated_at) : ''}
                          </span>
                        </div>
                        <div
                          className={`fw-medium text-truncate small ${isActive ? 'text-primary' : 'text-dark'}`}
                          style={{ fontSize: '0.82rem' }}
                          title={conv.title}
                        >
                          {conv.title}
                        </div>
                      </div>

                      {/* Delete conversation button */}
                      <button
                        type="button"
                        className="btn btn-sm btn-link text-muted p-1 hover-danger opacity-75"
                        onClick={(e) => handlePromptDelete(e, conv)}
                        title="Delete conversation"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Backdrop for mobile drawer */}
        {isMobileSidebarOpen && (
          <div
            className="position-fixed top-0 start-0 w-100 h-100 bg-dark bg-opacity-50 d-lg-none"
            style={{ zIndex: 1040 }}
            onClick={() => setIsMobileSidebarOpen(false)}
          />
        )}

        {/* =========================================================================
            MAIN PANEL: Active Conversation & Messages Area
            ========================================================================= */}
        <div className="col-lg-9 col-12 d-flex flex-column">
          <div
            className="card card-industrial flex-grow-1 d-flex flex-column p-0 bg-white shadow-sm"
            style={{ minHeight: '520px', maxHeight: '72vh' }}
          >
            {/* Chat Body */}
            <div className="card-body p-3 p-md-4 overflow-auto flex-grow-1">
              {!selectedMachineId ? (
                <EmptyState
                  title="No Machine Selected"
                  description="Choose an authorized machine from the dropdown above to query its OEM technical manuals."
                  icon={Cpu}
                />
              ) : isLoadingMessages ? (
                <div className="py-5 text-center">
                  <LoadingSpinner text="Retrieving conversation history & manual citations..." />
                </div>
              ) : messages.length === 0 ? (
                <EmptyState
                  title={`Ready for questions on ${currentMachine?.name || 'Machine'}`}
                  description="Ask about operating procedures, torque tolerances, relief valve thresholds, or troubleshooting fault codes directly verified by OEM manuals."
                  icon={MessageSquare}
                />
              ) : (
                messages.map((msg, index) => (
                  <ChatMessage
                    key={msg.id || `msg-${index}`}
                    message={msg}
                    machineName={currentMachine?.name || activeConversation?.machine_name}
                    onOpenPdf={handleOpenPdf}
                  />
                ))
              )}

              {/* Pending message spinner */}
              {isSending && (
                <div className="d-flex justify-content-start align-items-start gap-2 mb-3">
                  <div className="p-2 rounded-circle bg-dark text-white flex-shrink-0">
                    <Bot size={16} />
                  </div>
                  <div className="chat-bubble-assistant">
                    <div className="d-flex align-items-center gap-2 text-muted py-1">
                      <span className="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true" />
                      <span className="small">Synthesizing verified response from {currentMachine?.name || 'manual'}...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Bottom Fixed Message Input */}
            <ChatInput
              onSendMessage={handleSendMessage}
              disabled={!selectedMachineId || isSending}
              isSending={isSending}
              placeholder={
                !selectedMachineId
                  ? 'Select an authorized machine first...'
                  : `Ask a question about ${currentMachine?.name || 'this machine'}... (Press Enter to send)`
              }
            />
          </div>
        </div>
      </div>

      {/* Delete Conversation Confirmation Modal */}
      {deleteModal.isOpen && (
        <div className="modal fade show d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1060 }}>
          <div className="modal-dialog modal-dialog-centered modal-sm">
            <div className="modal-content border-0 shadow">
              <div className="modal-header bg-danger text-white py-2">
                <div className="d-flex align-items-center gap-2">
                  <Trash2 size={16} />
                  <h6 className="modal-title fw-bold mb-0">Delete Conversation?</h6>
                </div>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => !deleteModal.isDeleting && setDeleteModal({ isOpen: false, conversationId: null, title: '', isDeleting: false })}
                  disabled={deleteModal.isDeleting}
                />
              </div>
              <div className="modal-body p-3">
                <p className="small text-dark mb-0">
                  Are you sure you want to delete <strong>"{deleteModal.title}"</strong>? All messages and citations in this conversation will be permanently removed.
                </p>
              </div>
              <div className="modal-footer bg-light py-2">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => setDeleteModal({ isOpen: false, conversationId: null, title: '', isDeleting: false })}
                  disabled={deleteModal.isDeleting}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-danger d-flex align-items-center gap-1"
                  onClick={handleConfirmDelete}
                  disabled={deleteModal.isDeleting}
                >
                  {deleteModal.isDeleting ? (
                    <>
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <span>Delete</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PDF Viewer Modal */}
      <PdfViewerModal
        isOpen={pdfModal.isOpen}
        onClose={() => setPdfModal((prev) => ({ ...prev, isOpen: false }))}
        documentId={pdfModal.documentId}
        documentTitle={pdfModal.documentTitle}
        revision={pdfModal.revision}
        pageNumber={pdfModal.pageNumber}
        directPdfUrl={pdfModal.directPdfUrl}
      />
    </div>
  );
}
