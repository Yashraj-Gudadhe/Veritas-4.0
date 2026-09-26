import { useState, useRef, useCallback, useEffect } from 'react';

const SendIcon = ({ sending }) => sending ? (
  <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} aria-hidden="true" />
) : (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);

const ClipIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
  </svg>
);

const CloseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

const FileIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>
);

export default function ChatInput({ onSend, disabled, placeholder = 'Ask VERITAS a medical question…' }) {
  const [value, setValue] = useState('');
  const [file, setFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
  }, [value, filePreview]);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (!selected) return;
    
    // Check max size (e.g. 10MB)
    if (selected.size > 10 * 1024 * 1024) {
      alert("File is too large. Maximum allowed size is 10 MB.");
      return;
    }
    
    setFile(selected);
    if (selected.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setFilePreview(e.target.result);
      reader.readAsDataURL(selected);
    } else {
      setFilePreview(selected.name);
    }
  };

  const removeFile = () => {
    setFile(null);
    setFilePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if ((!trimmed && !file) || disabled) return;
    
    onSend(trimmed, file);
    
    setValue('');
    removeFile();
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, file, disabled, onSend]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  return (
    <div className="input-area">
      <div className="input-container">
        
        {filePreview && (
          <div className="attachment-preview">
            {file && file.type.startsWith('image/') ? (
              <img src={filePreview} alt="upload preview" className="preview-image" />
            ) : (
              <div className="preview-file">
                <FileIcon /> <span>{filePreview}</span>
              </div>
            )}
            <button className="remove-btn" onClick={removeFile} aria-label="Remove attachment"><CloseIcon/></button>
          </div>
        )}

        <div className="input-box" role="form" aria-label="Message input">
          <button 
            type="button"
            className="attach-btn" 
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            aria-label="Attach file"
          >
            <ClipIcon />
          </button>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            style={{ display: 'none' }} 
            accept="image/*,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          />

          <textarea
            id="chat-message-input"
            ref={textareaRef}
            className="message-textarea"
            placeholder={placeholder}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            rows={1}
            aria-label="Type your message"
            aria-disabled={disabled}
          />
          <button
            id="send-message-btn"
            className="send-btn"
            onClick={handleSubmit}
            disabled={(!value.trim() && !file) || disabled}
            aria-label="Send message"
            title={disabled ? 'Waiting for response…' : 'Send (Enter)'}
          >
            <SendIcon sending={disabled} />
          </button>
        </div>
        <p className="input-hint">
          Press <kbd style={{ background: 'var(--bg-hover)', padding: '0 4px', borderRadius: 3, fontSize: '0.68rem' }}>Enter</kbd> to send ·{' '}
          <kbd style={{ background: 'var(--bg-hover)', padding: '0 4px', borderRadius: 3, fontSize: '0.68rem' }}>Shift+Enter</kbd> for newline
        </p>
      </div>
    </div>
  );
}
