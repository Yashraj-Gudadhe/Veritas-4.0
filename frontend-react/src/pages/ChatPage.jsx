import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Sidebar from '../components/Sidebar';
import ChatMessage, { TypingMessage } from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import {
  listConversations,
  createConversation,
  getConversation,
  sendMessage,
  uploadAttachment,
} from '../api/chat';

// --- Icons ---
const MenuIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
);

const ShieldIcon = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    <path d="m9 12 2 2 4-4"/>
  </svg>
);

const SAMPLE_PROMPTS = [
  { title: 'Blood pressure analysis', sub: 'Evaluate a BP reading against clinical guidelines' },
  { title: 'Medication interaction', sub: 'Check evidence for drug interactions' },
  { title: 'Lab result interpretation', sub: 'Review lab values against reference ranges' },
  { title: 'Clinical guideline lookup', sub: 'Find authoritative sources on a condition' },
];

export default function ChatPage() {
  const { chatId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [currentTitle, setCurrentTitle] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const messagesEndRef = useRef(null);
  const scrollAreaRef = useRef(null);

  const initials = user?.name
    ? user.name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()
    : 'U';

  // Auto-scroll to bottom
  const scrollToBottom = useCallback((smooth = true) => {
    messagesEndRef.current?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto' });
  }, []);

  // Load sidebar conversation list
  const refreshConversations = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(data);
    } catch { /* noop */ }
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  // Load messages when chatId changes
  useEffect(() => {
    if (!chatId) {
      setMessages([]);
      setCurrentTitle('');
      setError('');
      return;
    }
    setLoadingChat(true);
    setError('');
    getConversation(chatId)
      .then(data => {
        setCurrentTitle(data.title);
        // Messages from API don't carry veritas_result in the list—just content
        setMessages(data.messages.map(m => ({ ...m, veritasResult: null })));
        setTimeout(() => scrollToBottom(false), 50);
      })
      .catch(err => {
        if (err.response?.status === 404) {
          navigate('/chat');
        } else {
          setError('Failed to load conversation. Please try again.');
        }
      })
      .finally(() => setLoadingChat(false));
  }, [chatId, navigate, scrollToBottom]);

  // Scroll on new messages
  useEffect(() => {
    scrollToBottom();
  }, [messages, sending, scrollToBottom]);

  // Create a new chat (or navigate to /chat for blank state)
  const handleNewChat = useCallback(() => {
    setMessages([]);
    setCurrentTitle('');
    setError('');
    navigate('/chat');
  }, [navigate]);

  // Send a message
  const handleSend = useCallback(async (content, file = null) => {
    if (sending) return;
    setError('');

    let activeChatId = chatId;

    // If no active chat, create one first
    if (!activeChatId) {
      try {
        const newConv = await createConversation('New Conversation');
        activeChatId = newConv.id;
        navigate(`/chat/${newConv.id}`, { replace: true });
        setConversations(prev => [newConv, ...prev]);
      } catch (e) {
        setError('Failed to start conversation. Please try again.');
        return;
      }
    }

    // Optimistically add user message
    let displayContent = content;
    if (file) {
      displayContent = `[Attached: ${file.name}]\n${content}`;
    }

    const tempUserMsg = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: displayContent,
      created_at: new Date().toISOString(),
      veritasResult: null,
    };
    setMessages(prev => [...prev, tempUserMsg]);
    setSending(true);

    try {
      let attachmentId = null;
      if (file) {
        try {
          const attResp = await uploadAttachment(activeChatId, file);
          attachmentId = attResp.id;
        } catch (attErr) {
          setError('Failed to upload attachment. ' + (attErr.response?.data?.detail || attErr.message));
          setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
          setSending(false);
          return;
        }
      }

      const result = await sendMessage(activeChatId, { content, attachment_id: attachmentId });

      // Update conversation title if it changed (auto-titled from first message)
      if (result.conversation_title) {
        setCurrentTitle(result.conversation_title);
        setConversations(prev =>
          prev.map(c => c.id === activeChatId
            ? { ...c, title: result.conversation_title, updated_at: new Date().toISOString() }
            : c
          )
        );
      }

      // Add assistant message with veritas result
      const assistantMsg = {
        ...result.message,
        veritasResult: result.veritas_result,
      };
      setMessages(prev => [...prev, assistantMsg]);

      // Refresh sidebar to update message count + ordering
      refreshConversations();
    } catch (err) {
      const detail = err.response?.data?.detail || 'An error occurred. Please try again.';
      setError(detail);
      // Remove the optimistic user message on failure
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
    } finally {
      setSending(false);
    }
  }, [sending, chatId, navigate, refreshConversations]);

  const handlePromptClick = useCallback((prompt) => {
    handleSend(prompt.title);
  }, [handleSend]);

  const isNewChat = !chatId;

  return (
    <div className="app-layout">
      <Sidebar
        conversations={conversations}
        onNewChat={handleNewChat}
        onConversationsChange={setConversations}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="main-area">
        {/* Header */}
        <header className="chat-header">
          <button
            id="mobile-menu-btn"
            className="mobile-menu-btn"
            onClick={() => setSidebarOpen(v => !v)}
            aria-label="Toggle sidebar"
            aria-expanded={sidebarOpen}
          >
            <MenuIcon />
          </button>
          <span className="chat-header-title">
            {currentTitle || (isNewChat ? 'New Conversation' : 'Loading…')}
          </span>
        </header>

        {/* Messages */}
        <div className="messages-area" ref={scrollAreaRef} role="log" aria-live="polite" aria-label="Conversation">
          <div className="messages-container" role="list">
            {/* Welcome screen (no chat selected, no messages) */}
            {isNewChat && messages.length === 0 && (
              <div className="welcome-screen">
                <div className="welcome-logo">
                  <ShieldIcon />
                </div>
                <h2 className="welcome-title">VERITAS</h2>
                <p className="welcome-sub">
                  Evidence-Aware Medical Decision Intelligence.<br />
                  Ask a clinical question or upload a medical document for analysis.
                </p>
                <div className="welcome-prompts">
                  {SAMPLE_PROMPTS.map((p, i) => (
                    <button
                      key={i}
                      id={`prompt-${i}`}
                      className="prompt-card"
                      onClick={() => handlePromptClick(p)}
                    >
                      <div className="prompt-card-title">{p.title}</div>
                      <div className="prompt-card-sub">{p.sub}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Loading state */}
            {loadingChat && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                <span className="spinner" aria-label="Loading conversation…" />
              </div>
            )}

            {/* Error state */}
            {error && !sending && (
              <div className="error-state">
                <div className="error-icon">⚠️</div>
                <div className="error-title">Something went wrong</div>
                <div className="error-msg">{error}</div>
                <button className="retry-btn" onClick={() => setError('')}>Dismiss</button>
              </div>
            )}

            {/* Messages */}
            {!loadingChat && messages.map((msg, idx) => {
              let userQueryStr = "";
              if (msg.role === 'assistant') {
                const prevMsg = messages[idx - 1];
                if (prevMsg && prevMsg.role === 'user') {
                  userQueryStr = prevMsg.content;
                }
              }
              return (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  userInitials={initials}
                  chatId={chatId}
                  userQuery={userQueryStr}
                />
              );
            })}

            {/* Typing indicator */}
            {sending && <TypingMessage />}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={sending} />
      </div>
    </div>
  );
}
