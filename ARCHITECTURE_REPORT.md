# VERITAS 3.0 — Architecture & Technical Report

## 1. Project Idea & Purpose
**VERITAS 3.0** is an **evidence-auditing decision intelligence engine** tailored for the medical domain. Unlike typical RAG/LLM chatbots that blindly summarize documents and generate answers, VERITAS enforces a deterministic, evidence-first paradigm. It analyzes clinical text (e.g., patient PDFs), extracts claims, scores retrieved medical literature based on 5 dimensions of quality, detects conflicts across sources, checks for missing required context, and strictly gates the LLM’s final output. It is built for clinicians, medical researchers, or healthcare systems to ensure AI conclusions are completely traceable and empirically justified.

## 2. Tech Stack
**Backend:**
- **Language:** Python 3.10+
- **Framework:** FastAPI (0.110.0+), Uvicorn (0.28.0+)
- **Pipeline Orchestration:** LangGraph (0.2.0+), Langchain Core (0.3.0+)
- **Database & ORM:** SQLite via SQLAlchemy (2.0.0+)
- **Vector Search & ML:** Sentence-transformers (2.7.0+), faiss-cpu (1.8.0+), NumPy
- **Auth:** python-jose[cryptography] (3.3.0+), passlib[bcrypt] (1.7.4+)
- **Utilities:** PyMuPDF (1.24.0+) for PDF parsing, lxml (5.1.0+) for XML ingestion, httpx (0.27.0+)
- **Testing:** Pytest (8.0.0+), pytest-asyncio

**Frontend:**
- **Framework:** React 19.2.8
- **Tooling:** Vite 8.3.0
- **Routing:** React Router DOM (7.18.4)
- **HTTP Client:** Axios (1.20.0)
- **Markdown Rendering:** react-markdown (10.1.0), remark-gfm

**LLM Integrations:**
- **Primary:** xAI Grok / Groq (`llama-3.3-70b-versatile`)
- **Fallback:** Google Gemini (`gemini-1.5-flash`)

## 3. Annotated Directory Tree
```text
veritass-3.0/
├── backend/                            # FastAPI backend application
│   ├── app/
│   │   ├── auth/                       # JWT auth logic
│   │   ├── evidence/                   # Rule-based decision gating & conflict detection logic
│   │   ├── graph/                      # LangGraph StateGraph pipeline (workflow.py, nodes.py)
│   │   ├── ingestion/                  # PDF & MedlinePlus XML parsing scripts
│   │   ├── llm/                        # Orchestrator for Groq/Gemini/Fallback generation
│   │   ├── models/                     # SQLAlchemy ORM definitions (User, Conversation, Message, Attachment)
│   │   ├── normalization/              # Regex-based medical term standardizer
│   │   ├── retrieval/                  # FAISS local vector RAG orchestration
│   │   ├── routers/                    # REST API routes (auth.py, chats.py, account.py)
│   │   ├── schemas/                    # Pydantic data models (evidence.py, state.py)
│   │   ├── scoring/                    # VERITAS Evidence Quality heuristic evaluator
│   │   ├── sources/                    # API Adapters (FDA, WHO, CDC, NCBI, ClinicalTrials)
│   │   ├── utils/                      # Helper scripts (logger, caching)
│   │   ├── config.py                   # Pydantic BaseSettings for env vars
│   │   ├── database.py                 # SQLite Engine and SessionMaker setup
│   │   └── main.py                     # FastAPI app entry point and pipeline endpoints
│   ├── tests/                          # 25+ pytest scripts covering logic and models
│   └── requirements.txt                # Python backend dependencies
├── frontend-react/                     # React Vite SPA
│   ├── src/
│   │   ├── api/                        # Axios wrapper functions for interacting with backend
│   │   ├── components/                 # React UI pieces (Sidebar, ChatInput, EvidencePanel)
│   │   ├── context/                    # AuthContext for global state
│   │   ├── pages/                      # ChatPage, LoginPage
│   │   ├── App.jsx & main.jsx          # React app roots
│   │   └── index.css                   # Global styling
│   └── package.json                    
├── data/                               # Stored indices and demo documents
├── .env                                # Secrets and environment configuration
├── run.sh / run_backend.sh             # Linux/macOS start scripts
└── run.bat / run_fullstack.bat         # Windows start scripts
```

## 4. System Architecture
VERITAS features a **Decoupled Architecture** (React SPA frontend + FastAPI backend) connected via REST.
The most notable architectural component is the **LangGraph State Machine** inside the backend:
- **Pipeline over Prompting:** User inputs aren't simply passed to an LLM. They traverse a multi-step cyclical graph: `ingest_document` -> `extract_claims` -> `normalize_concepts` -> `generate_requirements` -> `retrieve_local` -> `conditional_online` -> `score_and_match` -> `detect_conflicts_and_missing` -> `decision_gate` -> `generate_explanation`.
- **Deterministic Decision Gating:** A purely programmatic step (`VeritasDecisionGate`) inspects the collected evidence and pre-empts the LLM, forcing the system into one of 5 strictly audited states (e.g., `CONFLICTING`, `SUPPORTED`, `NO_RELIABLE_CONCLUSION`).
- **Resilient Fallback:** The LLM orchestrator attempts Groq/xAI inference, falls back to Google Gemini on failure, and falls back to a purely deterministic Python string generator if both APIs fail.

## 5. Data Models & Database
Database: **SQLite** via **SQLAlchemy ORM**.

- **`User` Table:** 
  - `id` (String UUID), `email` (String, unique), `name` (String), `password_hash` (String), `is_active` (Boolean), `created_at`, `updated_at`.
- **`Conversation` Table:**
  - `id` (String UUID), `user_id` (FK -> users.id), `title` (String), `created_at`, `updated_at`.
- **`Message` Table:**
  - `id` (String UUID), `conversation_id` (FK -> conversations.id), `role` (String: user/assistant/system), `content` (Text), `veritas_result_json` (Text - stores fully serialized state of the evidence graph and scoring audit), `created_at`.
- **`Attachment` Table:**
  - `id` (String UUID), `conversation_id` (FK), `message_id` (FK), `filename`, `file_type`, `mime_type`, `file_size`, `storage_path`, `created_at`.

## 6. API & Interfaces
All endpoints are RESTful FastAPI routes, prefixed by `/api`.
- **Auth Routes (`/api/auth/*`):** `/login` (issues JWT), `/signup`.
- **Chat Routes (`/api/chats/*`):**
  - `POST /api/chats`: Create a conversation.
  - `GET /api/chats`: List user conversations.
  - `GET /api/chats/{chat_id}`: Get conversation details.
  - `POST /api/chats/{chat_id}/messages`: Accepts user message, triggers the `veritas_graph` LangGraph pipeline, saves message, and returns the audited LLM response.
  - `POST /api/chats/{chat_id}/attachments`: Upload documents tied to a chat.
  - `GET /api/chats/{chat_id}/messages/{message_id}/veritas`: Retrieves the raw JSON audit trace for an assistant message.
- **System Routes:**
  - `GET /api/health`: Node liveness and LLM configuration check.
  - `POST /api/index/medlineplus`: Forces the vector store to index the MedlinePlus XML files.
  - `POST /api/analyze`: Main pipeline invocation (used internally and for legacy testing).

## 7. Authentication & Authorization
- Uses **JSON Web Tokens (JWT)** for stateless session management.
- User passwords hashed via `passlib[bcrypt]`.
- Enforced on the backend via a `get_current_user` dependency (reading Bearer tokens from Headers).
- Frontend stores the token securely in React Context (`AuthContext`) and handles intercepting Axios requests.

## 8. Core Features & Modules
- **Evidence Quality Scoring (`scoring/evaluator.py`):** An algorithm assessing vector-retrieved text across Authority (30%), Relevance (25%), Recency (15%), Methodology (15%), and Traceability (15%) to yield a 0-100 score.
- **Missing Info Engine (`evidence/missing_detector.py`):** Assesses if a clinical claim lacks required context (e.g. diagnosing hypertension from one reading without seated repeats or symptom checks).
- **Conflict Detector (`evidence/conflict_detector.py`):** Compares retrieved evidence chunks and flags if Tier 1 sources explicitly disagree (e.g., AHA/ACC vs. ESC/ESH guidelines).
- **Source Router (`sources/router.py`):** Normalizes medical concepts (`normalization/medical_norm.py`) and routes API requests smartly (e.g., "blood_pressure" triggers WHO APIs, "metformin" triggers FDA APIs).

## 9. External Integrations
- **LLM APIs:** Groq API (`llama-3.3-70b-versatile`), Google Gemini API (`gemini-1.5-flash`), xAI Grok (optional fallback).
- **Medical Authority APIs (`app/sources/`):**
  - World Health Organization (WHO GHO OData)
  - openFDA (Medication labels and effects)
  - CDC Open Data SODA
  - ClinicalTrials.gov
  - NCBI PubMed E-utilities
  - NLM Clinical Tables (FHIR/ICD-10)

## 10. Configuration & Environments
- **Environment Management:** Uses a root `.env` file (parsed by `python-dotenv` and loaded into a Pydantic `BaseSettings` object in `app/config.py`).
- **Key Vars:**
  - `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`
  - `GROQ_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`
  - `FDA_API_KEY`, `WHO_API_BASE_URL`
  - `CHROMA_PERSIST_DIRECTORY` (Note: FAISS is actively used, variable might be a legacy holdover).
  - `DEBUG`, `PORT`, `HOST`

## 11. Build, Test & Deployment
- **Local Dev Scripts:** `run.sh` / `run_backend.sh` (Linux) and `run.bat` / `run_fullstack.bat` (Windows) configure `PYTHONPATH` and boot Uvicorn + Vite dev servers.
- **Testing:** `pytest` configured via `pytest.ini`. 25+ tests evaluating logic gates, vector matching, and demo scenarios. `PYTHONPATH=backend python -m pytest backend/tests/ -v`.
- **CI/CD & Deployment:** No GitHub Actions, CI pipeline configs, Kubernetes manifests, or Dockerfiles exist in the repository root. Currently optimized for local prototyping.

## 12. Notable Patterns, TODOs & Known Issues
- **Anti-Hallucination Design:** The most distinct pattern is relying heavily on hard-coded deterministic Python logic for gating answers (`decision_gate.py`) and only feeding the LLM heavily filtered, scored evidence chunks.
- **In-Memory / Local FAISS:** Bypasses cloud vector databases (Pinecone, Weaviate) explicitly in favor of `faiss-cpu` and `sentence-transformers` for guaranteed offline privacy and zero-latency lookups.
- **State Storage Overhead (Technical Debt):** The `Message.veritas_result_json` field stores the entire evidence graph for every generated message. Over a long lifecycle, this SQLite field could lead to database bloat.
- **Open TODO:** Transitioning from SQLite to PostgreSQL is recommended for a production deployment, along with Dockerizing the application via a multi-stage `Dockerfile`.
