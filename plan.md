## Implementation Plan

### What data is available but not shown in React UI
The following fields from the `veritas_result_json` (API response) are rendered in the old HTML UI (`app.js`) but are missing from the React UI (`EvidencePanel.jsx`):
- `observations`: The structured quantitative findings (e.g., patient vitals, lab results) which were previously shown in the "Findings Grid".
- `graph_nodes` & `graph_links`: The data for the interactive SVG Evidence Graph (radial layout showing relationships between claims and evidence).
- `final_explanation`: The fallback deterministic explanation (currently the React UI just uses the LLM response message content).

### Files to be created
*(No new files need to be created as all required components are already present or can be integrated into existing ones per the constraints).*

### Files to be modified
- `frontend-react/src/components/ChatMessage.jsx`: 
  - Move the decision gate verdict badge and quality score *inside* the `EvidencePanel` so they only appear when the panel expands, as requested.
  - Ensure `sanitizeContent` robustly strips `[EV-XXX]` tags.
- `frontend-react/src/components/EvidencePanel.jsx`: 
  - Update the panel to include the decision verdict badge and overall score inside the expanded section.
  - Refine styling (color-coded badges, missing info as orange warnings, conflicts as red alerts).
- `backend/app/llm/orchestrator.py`: 
  - Ensure the LLM system prompt explicitly forbids the use of `[EV-001]` style citation tags and enforces markdown structure (headers, bolding, lists).

### Component breakdown
- `EvidencePanel` (Modified):
  - **Props**: `veritasResult` (object), `chatId` (string), `messageId` (string).
  - **Renders**: A toggle button. When expanded, shows the decision gate verdict (colored badge), overall score, supporting/conflicting/questionable sources (mapped to authority names without EV codes), missing info flags (orange), and conflicts (red).
- `ChatMessage` (Modified):
  - **Props**: `message` (object), `userInitials` (string), `chatId` (string).
  - **Renders**: The assistant message text (parsed via `react-markdown`), sanitized of any EV codes. Renders the `EvidencePanel` below the message bubble.
