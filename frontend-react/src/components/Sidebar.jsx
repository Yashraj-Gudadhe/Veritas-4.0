import { useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { useAuth } from '../context/AuthContext';
import { deleteConversation, renameConversation } from '../api/chat';

// -- Icons --
const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);
const ShieldIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    <path d="m9 12 2 2 4-4"/>
  </svg>
);
const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
  </svg>
);
const EditIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
);
const SearchIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
);
const AccountIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
  </svg>
);
const LogoutIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

// Group conversations by recency
function groupByDate(conversations) {
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yStr = yesterday.toDateString();
  const weekAgo = new Date(now);
  weekAgo.setDate(weekAgo.getDate() - 7);

  const groups = { Today: [], Yesterday: [], 'Previous 7 Days': [], Older: [] };
  for (const conv of conversations) {
    const d = new Date(conv.updated_at);
    const dStr = d.toDateString();
    if (dStr === today) groups.Today.push(conv);
    else if (dStr === yStr) groups.Yesterday.push(conv);
    else if (d >= weekAgo) groups['Previous 7 Days'].push(conv);
    else groups.Older.push(conv);
  }
  return groups;
}

export default function Sidebar({ conversations, onNewChat, onConversationsChange, isOpen, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { chatId } = useParams();

  const [search, setSearch] = useState('');
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  const filtered = search
    ? conversations.filter(c => c.title.toLowerCase().includes(search.toLowerCase()))
    : conversations;

  const groups = groupByDate(filtered);

  const handleDelete = useCallback(async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation?')) return;
    try {
      await deleteConversation(id);
      onConversationsChange(prev => prev.filter(c => c.id !== id));
      if (chatId === id) navigate('/chat');
    } catch { /* noop */ }
  }, [chatId, navigate, onConversationsChange]);

  const handleStartRename = useCallback((e, conv) => {
    e.stopPropagation();
    setRenamingId(conv.id);
    setRenameValue(conv.title);
  }, []);

  const handleRenameSubmit = useCallback(async (id) => {
    if (!renameValue.trim()) return;
    try {
      const updated = await renameConversation(id, renameValue.trim());
      onConversationsChange(prev => prev.map(c => c.id === id ? { ...c, title: updated.title } : c));
    } catch { /* noop */ }
    setRenamingId(null);
  }, [renameValue, onConversationsChange]);

  const initials = user?.name
    ? user.name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()
    : '?';

  return (
    <>
      {/* Mobile overlay */}
      <div
        className={`sidebar-overlay${isOpen ? ' visible' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <nav className={`sidebar${isOpen ? ' open' : ''}`} aria-label="Sidebar">
        {/* Logo */}
        <div className="sidebar-top">
          <div className="sidebar-logo">
            <div className="logo-icon">
              <img src="/veritas-logo.png" alt="VERITAS" style={{ height: "2rem", width: "auto", mixBlendMode: "multiply" }} />
            </div>
            <div>
              <div className="logo-text">VERITAS</div>
              <div className="logo-sub">Medical Evidence AI</div>
            </div>
          </div>

          <button id="new-chat-btn" className="new-chat-btn" onClick={() => { onNewChat(); onClose(); }}>
            <PlusIcon /> New Chat
          </button>
        </div>

        {/* Search */}
        <div className="sidebar-search">
          <div style={{ position: 'relative' }}>
            <span style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
              <SearchIcon />
            </span>
            <input
              id="sidebar-search"
              type="search"
              className="search-input"
              placeholder="Search conversations…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 28 }}
            />
          </div>
        </div>

        {/* Chat list */}
        <div className="sidebar-list">
          {filtered.length === 0 && (
            <div style={{ padding: '20px 12px', color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center' }}>
              {search ? 'No matches found' : 'No conversations yet'}
            </div>
          )}
          {Object.entries(groups).map(([label, items]) =>
            items.length > 0 && (
              <div key={label}>
                <div className="chat-group-label">{label}</div>
                {items.map(conv => (
                  <div
                    key={conv.id}
                    id={`chat-item-${conv.id}`}
                    className={`chat-item${chatId === conv.id ? ' active' : ''}`}
                    onClick={() => { navigate(`/chat/${conv.id}`); onClose(); }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && navigate(`/chat/${conv.id}`)}
                    aria-label={`Open conversation: ${conv.title}`}
                    aria-current={chatId === conv.id ? 'page' : undefined}
                  >
                    {renamingId === conv.id ? (
                      <input
                        className="chat-item-rename-input"
                        value={renameValue}
                        onChange={e => setRenameValue(e.target.value)}
                        onBlur={() => handleRenameSubmit(conv.id)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') handleRenameSubmit(conv.id);
                          if (e.key === 'Escape') setRenamingId(null);
                        }}
                        onClick={e => e.stopPropagation()}
                        autoFocus
                      />
                    ) : (
                      <>
                        <span className="chat-item-title">{conv.title}</span>
                        <span className="chat-item-actions" onClick={e => e.stopPropagation()}>
                          <button
                            id={`rename-${conv.id}`}
                            className="icon-btn"
                            title="Rename"
                            onClick={e => handleStartRename(e, conv)}
                          ><EditIcon /></button>
                          <button
                            id={`delete-${conv.id}`}
                            className="icon-btn danger"
                            title="Delete"
                            onClick={e => handleDelete(e, conv.id)}
                          ><TrashIcon /></button>
                        </span>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </div>

        {/* User footer */}
        <div className="sidebar-footer">
          {showUserMenu && (
            <div className="dropdown-menu" role="menu">
              <button id="go-account-btn" className="dropdown-item" role="menuitem" onClick={() => { navigate('/account'); setShowUserMenu(false); onClose(); }}>
                <AccountIcon /> My Account
              </button>
              <div className="dropdown-divider" />
              <button id="logout-btn" className="dropdown-item danger" role="menuitem" onClick={() => { logout(); navigate('/login'); }}>
                <LogoutIcon /> Log Out
              </button>
            </div>
          )}
          <button
            id="user-menu-btn"
            className="user-menu-btn"
            onClick={() => setShowUserMenu(v => !v)}
            aria-label="Open user menu"
            aria-expanded={showUserMenu}
          >
            <div className="user-avatar" aria-hidden="true">{initials}</div>
            <div className="user-info">
              <div className="user-name">{user?.name}</div>
              <div className="user-email">{user?.email}</div>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
              <polyline points="18 15 12 9 6 15"/>
            </svg>
          </button>
        </div>
      </nav>
    </>
  );
}
