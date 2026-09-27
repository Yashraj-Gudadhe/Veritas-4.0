# VERITAS 3.0 Technology Stack

## Languages & Runtime
- **Python**: 3.10+
- **Node.js**: Required runtime for Vite and React 19.

## Backend Framework
- **FastAPI** (`>=0.110.0`): Serves the REST API endpoints and acts as the high-performance backend controller.
- **Uvicorn** (`>=0.28.0`): The ASGI web server used to run the FastAPI application.

## AI & LLM
- **LangGraph** (`>=0.2.0`) & **LangChain Core** (`>=0.3.0`): Orchestrates the core pipeline, defining a state machine (`veritas_graph`) that flows from extraction to retrieval, scoring, and explanation.
- **LLM Providers**:
  - **Groq** (`llama-3.3-70b-versatile`): Primary fast reasoning engine.
  - **Google Gemini** (`gemini-1.5-flash`): Primary fallback mechanism on Groq failure.
  - **xAI / Grok**: Configurable alternative reasoning model.
  - **Fallback Order**: Groq → Gemini (or xAI) → Deterministic string generation.

## Vector Search & Embeddings
- **sentence-transformers** (`>=2.7.0`): Generates embedding vectors for clinical text and retrieved documents.
- **FAISS (faiss-cpu)** (`>=1.8.0`): Local, in-memory vector database used for indexing and retrieving MedlinePlus XML data, ensuring zero-latency lookups and offline privacy.

## Database & ORM
- **SQLite**: Local relational database (`backend/data/veritas.db`).
- **SQLAlchemy** (`>=2.0.0`): Object-Relational Mapper (ORM). 
  - **Schema Overview**: Maps tables for `User`, `Conversation`, `Message` (which stores the serialized LangGraph state in `veritas_result_json`), and `Attachment`.

## Authentication
- **python-jose[cryptography]** (`>=3.3.0`): Generates and verifies JSON Web Tokens (JWT) for stateless API session management.
- **passlib[bcrypt]** (`>=1.7.4`): Used to securely hash and verify user passwords before database storage.

## PDF & Document Processing
- **PyMuPDF** (`>=1.24.0`): Parses text out of uploaded patient PDFs.
- **lxml** (`>=5.1.0`): Parses large, complex MedlinePlus XML files for vector indexing on application startup.

## Medical Data Sources
External APIs integrated via async adapters in `backend/app/sources/`:
- **WHO GHO OData** (`who.py`): World Health Organization API for global health data and vitals guidelines.
- **openFDA** (`fda.py`): Extracts medication labeling, usage limits, and adverse reaction data.
- **CDC Open Data SODA** (`cdc.py`): Communicable disease controls and prevention literature.
- **MedlinePlus (NLM)** (`medlineplus.py`): Patient-level baseline medical authority context (online fetch to supplement local XML).
- **NCBI PubMed E-utilities** (`ncbi.py`): Academic literature references.
- **ClinicalTrials.gov** (`clinicaltrials.py`): Trial-specific investigational data.
- **NLM Clinical Tables** (`nlm_fhir.py`): FHIR / ICD-10 standardized ontology fetching.
- **ICMR** (`icmr.py`): Indian Council of Medical Research guidelines.

## Frontend
- **React** (`^19.2.8`): Primary UI framework.
- **Vite** (`^8.3.0`): Fast bundler and development server.
- **React Router DOM** (`^7.18.4`): Handles Single Page Application (SPA) routing (e.g., Login vs Chat pages).
- **Axios** (`^1.20.0`): HTTP client used to interface with the FastAPI backend, complete with JWT interceptors.
- **react-markdown** (`^10.1.0`) & **remark-gfm** (`^4.0.1`): Parses and safely renders the LLM's markdown explanations into the chat UI.

## Dev & Testing
- **Pytest** (`>=8.0.0`) & **pytest-asyncio** (`>=0.23.0`): Testing framework covering API endpoints, LangGraph progression, deterministic gates, and LLM failover logic.
- **Start Scripts**: `./run.sh`, `./run_backend.sh`, `./run_frontend.sh` (Linux/macOS) and `run.bat`, `run_fullstack.bat` (Windows).

## Infrastructure
- **Local Only:** No Docker, Docker-Compose, or CI/CD pipelines (e.g. GitHub Actions) are implemented. The repository is configured strictly for local iteration.
- **Future Production Requirement:** Migration from SQLite to PostgreSQL is recommended to support concurrency without database locking.
