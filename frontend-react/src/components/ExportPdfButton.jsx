import { useState } from 'react';
import { createPortal } from 'react-dom';
import { getVeritasResult } from '../api/chat';
import PdfExportTemplate from './PdfExportTemplate';

export default function ExportPdfButton({ chatId, messageId, veritasResult, userQuery }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(veritasResult || null);
  const [renderPdf, setRenderPdf] = useState(false);

  const handleExport = async () => {
    let currentData = data;
    if (!currentData) {
      setLoading(true);
      try {
        currentData = await getVeritasResult(chatId, messageId);
        setData(currentData);
      } catch (err) {
        console.error("Failed to fetch veritas result for PDF export", err);
        setLoading(false);
        return;
      }
      setLoading(false);
    }
    
    setRenderPdf(true);
    // Wait for the portal to render the PDF content before triggering print
    setTimeout(() => {
      window.print();
      setRenderPdf(false);
    }, 150);
  };

  return (
    <>
      <button 
        className="ep-toggle-btn"
        onClick={handleExport}
        disabled={loading}
      >
        {loading ? 'Generating...' : '📄 Export PDF'}
      </button>

      {renderPdf && data && createPortal(
        <PdfExportTemplate veritasResult={data} query={userQuery} />,
        document.body
      )}
    </>
  );
}
