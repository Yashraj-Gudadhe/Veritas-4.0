import React from 'react';

const formatObservationValue = (value) => {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      if (parsed.formatted) return parsed.formatted;
      if (parsed.systolic && parsed.diastolic) 
        return parsed.systolic + '/' + parsed.diastolic;
      return value;
    } catch {
      return value;
    }
  }
  if (typeof value === 'object' && value !== null) {
    if (value.formatted) return value.formatted;
    if (value.systolic && value.diastolic) 
      return value.systolic + '/' + value.diastolic;
    return JSON.stringify(value);
  }
  return value ?? 'N/A';
};

const stripMarkdown = (text) => {
  if (!text) return '';
  return text
    .replace(/#{1,6}\s*/g, '')        // remove ## headers
    .replace(/\*\*(.*?)\*\*/g, '$1')  // remove **bold**
    .replace(/\*(.*?)\*/g, '$1')      // remove *italic*
    .replace(/^\s*[-*+]\s/gm, '• ')   // convert bullet markers to •
    .replace(/\n{3,}/g, '\n\n')       // collapse excess newlines
    .trim();
};

export default function PdfExportTemplate({ veritasResult, query }) {
  if (!veritasResult) return null;

  const {
    document_name,
    user_query,
    decision_status,
    evidence_quality_score,
    human_review_required,
    audit_record,
    final_explanation,
    score_breakdown,
    observations = [],
    claims = [],
    supporting_evidence = [],
    conflicting_evidence = [],
    questionable_evidence = [],
    contradictions = [],
    missing_information = []
  } = veritasResult;

  const timestamp = audit_record?.timestamp || new Date().toISOString();
  const queryToDisplay = (user_query || query || "N/A")
    .replace(/^\[Attached:.*?\]\n?/i, '')
    .trim();

  const renderEvidenceList = (list) => {
    if (!list || list.length === 0) return <p>No data found for this section.</p>;
    return (
      <ul className="pdf-evidence-list">
        {list.map((ev, i) => (
          <li key={i} className="pdf-evidence-item">
            <strong>{ev.source_name || "Unknown Source"}</strong> (Tier {ev.authority_tier || "N/A"}) - Score: {ev.evidence_score != null ? ev.evidence_score : "N/A"}
            <p>{ev.text}</p>
            {ev.url && <p className="pdf-url">URL: {ev.url}</p>}
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="pdf-hidden" id="pdf-export-container">
      {/* Page 1: Header */}
      <div className="pdf-page">
        <h1>VERITAS Clinical Evidence Report</h1>
        <div className="pdf-header-data">
          <p><strong>Document Name:</strong> {document_name || "Unknown Document"}</p>
          <p><strong>User Query:</strong> {queryToDisplay}</p>
          <p><strong>Decision Status:</strong> <span className={`pdf-status pdf-status-${decision_status?.toLowerCase()}`}>{decision_status || "N/A"}</span></p>
          <p><strong>Evidence Quality Score:</strong> {evidence_quality_score != null ? evidence_quality_score : "N/A"}</p>
          <p><strong>Human Review Required:</strong> {human_review_required ? "Yes" : "No"}</p>
          <p><strong>Generated At:</strong> {new Date(timestamp).toLocaleString()}</p>
        </div>
      </div>

      {/* Page 2: Clinical Assessment */}
      <div className="pdf-page">
        <h2>Clinical Assessment</h2>
        
        <h3>Final Explanation</h3>
        <p style={{ whiteSpace: 'pre-wrap' }}>{stripMarkdown(final_explanation) || "No explanation provided"}</p>

        <h3>Score Breakdown</h3>
        {score_breakdown ? (
          <table className="pdf-table">
            <tbody>
              <tr><td>Composite Score</td><td>{score_breakdown.composite_veritas_score ?? "N/A"}</td></tr>
              <tr><td>Quality Tier</td><td>{score_breakdown.quality_tier || "N/A"}</td></tr>
              <tr><td>Authority</td><td>{score_breakdown.authority_pct ?? "N/A"}%</td></tr>
              <tr><td>Relevance</td><td>{score_breakdown.relevance_pct ?? "N/A"}%</td></tr>
              <tr><td>Recency</td><td>{score_breakdown.recency_pct ?? "N/A"}%</td></tr>
              <tr><td>Methodology</td><td>{score_breakdown.methodology_pct ?? "N/A"}%</td></tr>
              <tr><td>Traceability</td><td>{score_breakdown.traceability_pct ?? "N/A"}%</td></tr>
            </tbody>
          </table>
        ) : <p>No score breakdown available.</p>}

        <h3>Extracted Observations</h3>
        {observations.length > 0 ? (
          <table className="pdf-table">
            <thead>
              <tr><th>Type</th><th>Name</th><th>Value</th><th>Unit</th><th>Reference</th></tr>
            </thead>
            <tbody>
              {observations.map((obs, i) => (
                <tr key={i}>
                  <td>{obs.type}</td>
                  <td>{obs.name}</td>
                  <td>{formatObservationValue(obs.value)}</td>
                  <td>{obs.unit || "-"}</td>
                  <td>{obs.reference_range || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p>No observations extracted.</p>}

        <h3>Core Claims</h3>
        {claims.length > 0 ? (
          <ul className="pdf-list">
            {claims.map((claim, i) => (
              <li key={i}><strong>{claim.claim_type}:</strong> {claim.claim}</li>
            ))}
          </ul>
        ) : <p>No core claims extracted.</p>}
      </div>

      {/* Page 3: Evidence Audit Trail */}
      <div className="pdf-page">
        <h2>Evidence Audit Trail</h2>

        <h3>Supporting Evidence</h3>
        {renderEvidenceList(supporting_evidence)}

        <h3>Conflicting Evidence</h3>
        {renderEvidenceList(conflicting_evidence)}

        <h3>Questionable Evidence</h3>
        {renderEvidenceList(questionable_evidence)}
      </div>

      {/* Page 4: Flags & Warnings */}
      <div className="pdf-page">
        <h2>Flags & Warnings</h2>

        <h3>Guideline Conflicts Detected</h3>
        {contradictions.length > 0 ? (
          <div className="pdf-conflicts">
            {contradictions.map((c, i) => (
              <div key={i} className="pdf-conflict-item">
                <p><strong>{c.source_a_name || "Source A"}</strong> claims: <em>{c.source_a_claim}</em></p>
                <p><strong>{c.source_b_name || "Source B"}</strong> claims: <em>{c.source_b_claim}</em></p>
                <p><strong>Difference Reason:</strong> {c.difference_reason}</p>
              </div>
            ))}
          </div>
        ) : <p>No guideline conflicts detected.</p>}

        <h3>Missing Clinical Context</h3>
        {missing_information.length > 0 ? (
          <ul className="pdf-list">
            {missing_information.map((m, i) => (
              <li key={i}>
                <strong>{m.item} ({m.category})</strong>: {m.clinical_reason}
              </li>
            ))}
          </ul>
        ) : <p>No missing information flags.</p>}
      </div>

      {/* Page 5: Disclaimer */}
      <div className="pdf-page">
        <h2>Disclaimer</h2>
        <p className="pdf-disclaimer">
          This report is generated by VERITAS 3.0, an AI-powered clinical evidence assistant. 
          This information is intended to support, not replace, clinical judgment. 
          All findings must be independently verified by a qualified healthcare professional 
          before application to patient care.
        </p>
      </div>
    </div>
  );
}
