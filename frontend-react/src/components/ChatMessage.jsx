import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { format } from 'date-fns';
import EvidencePanel from './EvidencePanel';
import ExportPdfButton from './ExportPdfButton';

// Strip any residual [EV-001] style codes the LLM might still emit
function sanitizeContent(text) {
  if (!text) return '';
  return text.replace(/\[EV-\d+\]/gi, '').trim();
}

const DECISION_STATUS_MAP = {
  SUPPORTED: { label: 'Supported', cls: 'badge-supported' },
  CONFLICTING: { label: 'Conflicting Evidence', cls: 'badge-conflicting' },
  ADDITIONAL_INFORMATION_REQUIRED: { label: 'More Info Needed', cls: 'badge-missing' },
  QUESTIONABLE: { label: 'Questionable', cls: 'badge-questionable' },
  NO_RELIABLE_CONCLUSION: { label: 'No Conclusion', cls: 'badge-inconclusive' },
};

const UserAvatar = ({ initials }) => (
  <div className="message-avatar user-av" aria-hidden="true">{initials}</div>
);

const AssistantAvatar = () => (
  <div className="message-avatar assistant-av" aria-hidden="true">V</div>
);

function VeritasBadge({ status }) {
  const info = DECISION_STATUS_MAP[status] || { label: status, cls: 'badge-inconclusive' };
  return <span className={`veritas-badge ${info.cls}`}>{info.label}</span>;
}

function UserMessage({ message, initials }) {
  const ts = message.created_at
    ? format(new Date(message.created_at), 'HH:mm')
    : '';

  let displayContent = message.content;
  let attachedFile = null;

  if (message.attachment) {
    attachedFile = message.attachment.filename;
    displayContent = displayContent.replace(/^\[Attached: .*?\]\n?/, '');
  } else {
    const match = displayContent.match(/^\[Attached: (.*?)\]\n?/);
    if (match) {
      attachedFile = match[1];
      displayContent = displayContent.replace(match[0], '');
    }
  }

  return (
    <div className="message-row user" role="listitem">
      <UserAvatar initials={initials} />
      <div className="message-content">
        <div className="message-bubble">
          {attachedFile && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px', background: 'rgba(0,0,0,0.05)', borderRadius: '6px', marginBottom: '8px', fontSize: '0.85rem' }}>
              📄 {attachedFile}
            </div>
          )}
          {displayContent}
        </div>
        {ts && <div className="message-meta">{ts}</div>}
      </div>
    </div>
  );
}

function AssistantMessage({ message, veritasResult, chatId, userQuery }) {
  const ts = message.created_at
    ? format(new Date(message.created_at), 'HH:mm')
    : '';

  const status = veritasResult?.decision_status;
  const score = veritasResult?.evidence_quality_score;

  // Sanitize: strip any [EV-XXX] codes the LLM may have emitted
  const cleanContent = sanitizeContent(message.content);

  // Only show EvidencePanel for persisted messages (not temp IDs)
  const isPersistedMessage = message.id && !String(message.id).startsWith('temp-');

  return (
    <div className="message-row assistant" role="listitem">
      <AssistantAvatar />
      <div className="message-content">
        {status && (
          <div style={{ marginBottom: 6 }}>
            <VeritasBadge status={status} />
            {score != null && (
              <span className="score-chip">
                Quality Score: {Math.round(score)}/100
              </span>
            )}
          </div>
        )}
        <div className="message-bubble md-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {cleanContent || '_No response._'}
          </ReactMarkdown>
        </div>
        {ts && <div className="message-meta">{ts}</div>}

        {/* Evidence Panel — shown for all assistant messages that have/may have veritas data */}
        {isPersistedMessage && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <EvidencePanel
              veritasResult={veritasResult}
              chatId={chatId}
              messageId={message.id}
            />
            <ExportPdfButton
              chatId={chatId}
              messageId={message.id}
              veritasResult={veritasResult}
              userQuery={userQuery}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export function TypingMessage() {
  return (
    <div className="message-row assistant" role="status" aria-label="VERITAS is thinking…">
      <AssistantAvatar />
      <div className="message-content">
        <div className="typing-indicator" aria-hidden="true">
          <div className="typing-dot" />
          <div className="typing-dot" />
          <div className="typing-dot" />
        </div>
        <div className="message-meta" style={{ marginTop: 4 }}>VERITAS is analysing evidence…</div>
      </div>
    </div>
  );
}

export default function ChatMessage({ message, userInitials, chatId, userQuery }) {
  if (message.role === 'user') {
    return <UserMessage message={message} initials={userInitials} />;
  }
  return (
    <AssistantMessage
      message={message}
      veritasResult={message.veritasResult}
      chatId={chatId}
      userQuery={userQuery}
    />
  );
}
