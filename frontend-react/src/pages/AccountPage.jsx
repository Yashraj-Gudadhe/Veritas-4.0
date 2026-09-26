import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getAccount, updateAccount } from '../api/account';
import { format } from 'date-fns';

const BackIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <polyline points="15 18 9 12 15 6"/>
  </svg>
);

export default function AccountPage() {
  const { user, logout, updateUser } = useAuth();
  const navigate = useNavigate();

  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    getAccount()
      .then(data => {
        setAccount(data);
        setNameValue(data.name);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!nameValue.trim()) return;
    setSaving(true);
    try {
      const updated = await updateAccount({ name: nameValue.trim() });
      setAccount(prev => ({ ...prev, name: updated.name }));
      updateUser({ ...user, name: updated.name });
      setSaveMsg('Name updated!');
      setEditing(false);
      setTimeout(() => setSaveMsg(''), 2500);
    } catch (e) {
      setSaveMsg('Failed to update. Try again.');
    } finally {
      setSaving(false);
    }
  };

  const initials = account?.name
    ? account.name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()
    : '?';

  return (
    <div className="main-area">
      <div className="account-page">
        <div className="account-container">
          <div className="account-header">
            <button
              id="account-back-btn"
              className="account-back-btn"
              onClick={() => navigate(-1)}
              aria-label="Go back"
            >
              <BackIcon />
            </button>
            <h1 className="account-page-title">Account</h1>
          </div>

          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
              <span className="spinner" aria-label="Loading…" />
            </div>
          ) : (
            <>
              {/* Profile Section */}
              <div className="account-section">
                <div className="account-section-title">Profile</div>
                <div className="account-avatar-row">
                  <div className="account-avatar">{initials}</div>
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{account?.name}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>{account?.email}</div>
                  </div>
                </div>

                {saveMsg && (
                  <div className={`alert-banner ${saveMsg.includes('updated') ? 'success' : 'error'}`} style={{ marginBottom: 12 }}>
                    {saveMsg}
                  </div>
                )}

                {editing ? (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                    <input
                      id="edit-name-input"
                      className="form-input"
                      value={nameValue}
                      onChange={e => setNameValue(e.target.value)}
                      style={{ flex: 1 }}
                      autoFocus
                      onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setEditing(false); }}
                    />
                    <button
                      id="save-name-btn"
                      className="auth-submit-btn"
                      style={{ width: 'auto', padding: '0 16px' }}
                      onClick={handleSave}
                      disabled={saving}
                    >
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      id="cancel-edit-btn"
                      className="retry-btn"
                      onClick={() => { setEditing(false); setNameValue(account?.name); }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : null}

                <div className="account-row">
                  <span className="account-row-label">Display Name</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="account-row-value">{account?.name}</span>
                    {!editing && (
                      <button
                        id="edit-name-btn"
                        className="retry-btn"
                        style={{ padding: '4px 10px', fontSize: '0.75rem', marginTop: 0 }}
                        onClick={() => setEditing(true)}
                      >Edit</button>
                    )}
                  </span>
                </div>
                <div className="account-row">
                  <span className="account-row-label">Email</span>
                  <span className="account-row-value">{account?.email}</span>
                </div>
              </div>

              {/* Account Details */}
              <div className="account-section">
                <div className="account-section-title">Account Details</div>
                <div className="account-row">
                  <span className="account-row-label">Account Created</span>
                  <span className="account-row-value">
                    {account?.created_at ? format(new Date(account.created_at), 'MMM d, yyyy') : '—'}
                  </span>
                </div>
                <div className="account-row">
                  <span className="account-row-label">Authentication</span>
                  <span className="account-row-value">Email / Password</span>
                </div>
              </div>

              {/* Danger Zone */}
              <div className="account-section">
                <div className="account-section-title">Session</div>
                <button
                  id="account-logout-btn"
                  className="logout-btn"
                  onClick={() => { logout(); navigate('/login'); }}
                >
                  Log Out of VERITAS
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
