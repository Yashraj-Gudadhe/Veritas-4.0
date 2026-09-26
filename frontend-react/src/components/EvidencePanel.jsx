import { useState, useCallback } from 'react';
import { getVeritasResult } from '../api/chat';

// ── Authority name normalizer ──────────────────────────────────────────────
// Maps internal source_name strings / evidence_id prefixes to display names.
// No EV-XXX codes are ever shown to the user.
function normalizeAuthorityName(sourceName = '') {
  const s = sourceName.toLowerCase();
  if (s.includes('who') || s.includes('world health')) return 'WHO';
  if (s.includes('fda') || s.includes('food and drug')) return 'FDA';
  if (s.includes('cdc') || s.includes('centers for disease')) return 'CDC';
  if (s.includes('pubmed') || s.includes('ncbi') || s.includes('national library')) return 'PubMed / NCBI';
  if (s.includes('medlineplus') || s.includes('medline')) return 'MedlinePlus';
  if (s.includes('clinicaltrials') || s.includes('clinical trials')) return 'ClinicalTrials.gov';
  if (s.includes('nlm') || s.includes('national library of medicine')) return 'NLM';
  if (s.includes('icmr') || s.includes('indian council')) return 'ICMR';
  if (s.includes('nih') || s.includes('national institutes')) return 'NIH';
  if (s.includes('uptodate')) return 'UpToDate';
  if (s.includes('cochrane')) return 'Cochrane';
  if (s.includes('embase')) return 'Embase';
  // Return original with first letter capitalized if no match
  return sourceName.trim() || 'Unknown Source';
}

// ── Score bar sub-component ────────────────────────────────────────────────
function ScoreBar({ value, max = 100, colorClass = '' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="ep-score-bar-track">
      <div
        className={`ep-score-bar-fill ${colorClass}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Score tier helper ──────────────────────────────────────────────────────
function scoreTierClass(score) {
  if (score >= 80) return 'ep-score-high';
  if (score >= 55) return 'ep-score-moderate';
  return 'ep-score-low';
}

// ── Individual evidence source card ───────────────────────────────────────
function SourceCard({ ev, variant = 'supporting' }) {
  const [expanded, setExpanded] = useState(false);
  const authorityLabel = normalizeAuthorityName(ev.source_name);
  const score = typeof ev.evidence_score === 'number' ? Math.round(ev.evidence_score) : null;
  const text = ev.text || '';
  const PREVIEW_LEN = 180;
  const isLong = text.length > PREVIEW_LEN;
  const displayText = expanded || !isLong ? text : text.slice(0, PREVIEW_LEN).replace(/\s\S+$/, '') + '\u2026';

  const variantClass = {
    supporting: 'ep-card-supporting',
    conflicting: 'ep-card-conflicting',
    questionable: 'ep-card-questionable',
  }[variant] || 'ep-card-supporting';

  return (
    <div className={`ep-source-card ${variantClass}`}>
      <div className="ep-card-header">
        <span className={`ep-authority-chip ep-chip-${variant}`}>
          {authorityLabel}
        </span>
        {ev.authority_tier && (
          <span className="ep-tier-badge">Tier {ev.authority_tier}</span>
        )}
        {score !== null && (
          <span className={`ep-score-num ${scoreTierClass(score)}`}>
            {score}/100
          </span>
        )}
      </div>

      {ev.title && <div className="ep-card-title">{ev.title}</div>}

      {score !== null && (
        <div className="ep-score-row">
          <ScoreBar value={score} colorClass={scoreTierClass(score)} />
        </div>
      )}

      <p className="ep-card-excerpt">
        {displayText}
        {isLong && (
          <button
            className="ep-read-more-btn"
            onClick={() => setExpanded(v => !v)}
          >
            {expanded ? ' Read less' : ' Read more'}
          </button>
        )}
      </p>

      <div className="ep-card-footer">
        {ev.publication_date && (
          <span className="ep-meta-tag">Published: {ev.publication_date}</span>
        )}
        {ev.quality_label && (
          <span className="ep-meta-tag">{ev.quality_label}</span>
        )}
        {ev.url && (
          <a
            href={ev.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ep-source-link"
          >
            View Source &rarr;
          </a>
        )}
      </div>
    </div>
  );
}

// ── Contradiction / conflict item ─────────────────────────────────────────
function ConflictItem({ contradiction }) {
  return (
    <div className="ep-conflict-item">
      <div className="ep-conflict-row">
        <div className="ep-conflict-col">
          <div className="ep-conflict-label">
            {normalizeAuthorityName(contradiction.source_a_name)}
          </div>
          <p className="ep-conflict-claim">{contradiction.source_a_claim}</p>
        </div>
        <div className="ep-conflict-vs">vs</div>
        <div className="ep-conflict-col">
          <div className="ep-conflict-label">
            {normalizeAuthorityName(contradiction.source_b_name)}
          </div>
          <p className="ep-conflict-claim">{contradiction.source_b_claim}</p>
        </div>
      </div>
      {contradiction.difference_reason && (
        <div className="ep-conflict-reason">
          <span className="ep-conflict-reason-label">Reason for divergence:</span>{' '}
          {contradiction.difference_reason}
        </div>
      )}
    </div>
  );
}

// ── Missing info item ─────────────────────────────────────────────────────
function MissingItem({ item }) {
  const catClass = {
    CRITICAL: 'ep-missing-critical',
    IMPORTANT: 'ep-missing-important',
    OPTIONAL: 'ep-missing-optional',
  }[item.category] || 'ep-missing-optional';

  return (
    <div className="ep-missing-item">
      <span className={`ep-missing-tag ${catClass}`}>{item.category}</span>
      <div className="ep-missing-body">
        <strong>{item.item}</strong>
        {item.clinical_reason && (
          <span className="ep-missing-reason"> &mdash; {item.clinical_reason}</span>
        )}
      </div>
    </div>
  );
}

// ── Score breakdown section ───────────────────────────────────────────────
function ScoreBreakdown({ breakdown, compositeScore }) {
  if (!breakdown) return null;
  const dims = [
    { label: 'Authority', key: 'authority_pct' },
    { label: 'Relevance', key: 'relevance_pct' },
    { label: 'Recency', key: 'recency_pct' },
    { label: 'Methodology', key: 'methodology_pct' },
    { label: 'Traceability', key: 'traceability_pct' },
  ];

  return (
    <div className="ep-score-breakdown">
      <div className="ep-score-composite">
        <span className={`ep-composite-num ${scoreTierClass(compositeScore)}`}>
          {Math.round(compositeScore)}
        </span>
        <span className="ep-composite-label">/ 100 &mdash; {breakdown.quality_tier || 'Evidence Quality'}</span>
      </div>
      <div className="ep-dim-grid">
        {dims.map(d => (
          <div key={d.key} className="ep-dim-row">
            <span className="ep-dim-label">{d.label}</span>
            <ScoreBar value={breakdown[d.key] || 0} max={100} colorClass={scoreTierClass(breakdown[d.key] || 0)} />
            <span className="ep-dim-val">{Math.round(breakdown[d.key] || 0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main EvidencePanel ─────────────────────────────────────────────────────
export default function EvidencePanel({ veritasResult: initialResult, chatId, messageId }) {
  const [isOpen, setIsOpen] = useState(false);
  const [veritasResult, setVeritasResult] = useState(initialResult || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasFetched, setHasFetched] = useState(!!initialResult);

  const handleToggle = useCallback(async () => {
    const opening = !isOpen;
    setIsOpen(opening);

    // Lazy-fetch on first open if we don't have the data yet
    if (opening && !hasFetched && chatId && messageId) {
      setLoading(true);
      setError(null);
      try {
        const result = await getVeritasResult(chatId, messageId);
        setVeritasResult(result);
        setHasFetched(true);
      } catch (e) {
        if (e.response?.status === 404) {
          setError('No evidence data available for this message.');
        } else {
          setError('Failed to load evidence data.');
        }
      } finally {
        setLoading(false);
      }
    }
  }, [isOpen, hasFetched, chatId, messageId]);

  const vr = veritasResult;
  const supporting = vr?.supporting_evidence || [];
  const conflicting = vr?.conflicting_evidence || [];
  const questionable = vr?.questionable_evidence || [];
  const contradictions = vr?.contradictions || [];
  const missing = vr?.missing_information || [];
  const allSources = supporting.length + conflicting.length + questionable.length;

  return (
    <div className="ep-container">
      {/* Toggle button */}
      <button
        className={`ep-toggle-btn ${isOpen ? 'ep-toggle-open' : ''}`}
        onClick={handleToggle}
        aria-expanded={isOpen}
        aria-controls={`ep-panel-${messageId}`}
        id={`ep-toggle-${messageId}`}
      >
        <span className="ep-toggle-icon">
          {isOpen ? '\u25BE' : '\u25B8'}
        </span>
        Sources &amp; Evidence
        {allSources > 0 && !isOpen && (
          <span className="ep-source-count">{allSources} source{allSources !== 1 ? 's' : ''}</span>
        )}
      </button>

      {/* Panel */}
      {isOpen && (
        <div
          className="ep-panel"
          id={`ep-panel-${messageId}`}
          role="region"
          aria-label="Evidence and sources"
        >
          {loading && (
            <div className="ep-loading">
              <span className="spinner" aria-label="Loading evidence\u2026" />
              <span>Loading evidence&hellip;</span>
            </div>
          )}

          {error && (
            <div className="ep-error">{error}</div>
          )}

          {!loading && !error && vr && (
            <>
              {/* Score Breakdown */}
              <ScoreBreakdown
                breakdown={vr.score_breakdown}
                compositeScore={vr.evidence_quality_score || 0}
              />

              {/* Human review notice */}
              {vr.human_review_required && (
                <div className="ep-human-review-banner">
                  &#9877; Human clinical review recommended for this finding.
                </div>
              )}

              {/* Supporting Sources */}
              {supporting.length > 0 && (
                <section className="ep-section">
                  <h4 className="ep-section-title ep-section-supporting">
                    &#10003; Supporting Evidence ({supporting.length})
                  </h4>
                  {supporting.map((ev, i) => (
                    <SourceCard key={ev.evidence_id || i} ev={ev} variant="supporting" />
                  ))}
                </section>
              )}

              {/* Conflicting Sources */}
              {conflicting.length > 0 && (
                <section className="ep-section">
                  <h4 className="ep-section-title ep-section-conflicting">
                    &#10007; Conflicting Evidence ({conflicting.length})
                  </h4>
                  {conflicting.map((ev, i) => (
                    <SourceCard key={ev.evidence_id || i} ev={ev} variant="conflicting" />
                  ))}
                </section>
              )}

              {/* Questionable Sources */}
              {questionable.length > 0 && (
                <section className="ep-section">
                  <h4 className="ep-section-title ep-section-questionable">
                    &#9888; Questionable Sources ({questionable.length})
                  </h4>
                  {questionable.map((ev, i) => (
                    <SourceCard key={ev.evidence_id || i} ev={ev} variant="questionable" />
                  ))}
                </section>
              )}

              {/* Contradictions */}
              {contradictions.length > 0 && (
                <section className="ep-section">
                  <h4 className="ep-section-title ep-section-conflict-title">
                    &#9889; Guideline Conflicts Detected ({contradictions.length})
                  </h4>
                  {contradictions.map((c, i) => (
                    <ConflictItem key={c.id || i} contradiction={c} />
                  ))}
                </section>
              )}

              {/* Missing Information */}
              {missing.length > 0 && (
                <section className="ep-section">
                  <h4 className="ep-section-title ep-section-missing">
                    &#9873; Missing Clinical Context ({missing.length})
                  </h4>
                  {missing.map((m, i) => (
                    <MissingItem key={m.id || i} item={m} />
                  ))}
                </section>
              )}

              {/* Empty state */}
              {allSources === 0 && contradictions.length === 0 && missing.length === 0 && (
                <div className="ep-empty">No evidence sources were retrieved for this response.</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
