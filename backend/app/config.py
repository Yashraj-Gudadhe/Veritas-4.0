import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)

class Settings(BaseModel):
    # App
    APP_NAME: str = "VERITAS — Evidence-Aware Decision Intelligence"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Base Directories
    BASE_DIR: Path = ROOT_DIR
    DATA_DIR: Path = ROOT_DIR / "backend" / "data"
    FIXTURES_DIR: Path = ROOT_DIR / "backend" / "data" / "fixtures"
    MEDLINEPLUS_DIR: Path = ROOT_DIR / "backend" / "data" / "medlineplus"
    CACHE_DIR: Path = ROOT_DIR / "backend" / "data" / "cache"

    # Primary LLM: Groq
    @property
    def GROQ_API_KEY(self) -> str:
        return os.getenv("GROQ_API_KEY", "")

    @property
    def GROQ_MODEL(self) -> str:
        return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    @property
    def GROQ_BASE_URL(self) -> str:
        return os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    GROQ_TIMEOUT_SEC: float = 15.0

    # Fallback LLM: Google Gemini
    @property
    def GEMINI_API_KEY(self) -> str:
        return os.getenv("GEMINI_API_KEY", "")

    @property
    def GEMINI_MODEL(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    GEMINI_TIMEOUT_SEC: float = 15.0

    # MedlinePlus XML configuration
    MEDLINEPLUS_XML_PATH: str = os.getenv("MEDLINEPLUS_XML_PATH", "backend/data/medlineplus/raw/mplus_topics.xml")

    # Authoritative Source Endpoints
    WHO_API_BASE_URL: str = os.getenv("WHO_API_BASE_URL", "https://ghoapi.azureedge.net/api")
    FDA_API_KEY: str = os.getenv("FDA_API_KEY", "")
    FDA_API_BASE_URL: str = os.getenv("FDA_API_BASE_URL", "https://api.fda.gov")

    # Vector Storage & Persistence
    CHROMA_PERSIST_DIRECTORY: str = os.getenv("CHROMA_PERSIST_DIRECTORY", "backend/data/medlineplus/index")
    CACHE_EXPIRY_HOURS: int = int(os.getenv("CACHE_EXPIRY_HOURS", "72"))

    # Evidence Scoring Weights (Formula: 30% Auth, 25% Rel, 15% Rec, 15% Meth, 15% Trac)
    WEIGHT_AUTHORITY: float = 0.30
    WEIGHT_RELEVANCE: float = 0.25
    WEIGHT_RECENCY: float = 0.15
    WEIGHT_METHODOLOGY: float = 0.15
    WEIGHT_TRACEABILITY: float = 0.15

    # Thresholds for Decision Gates
    DECISION_THRESHOLD_HIGH: float = 85.0
    DECISION_THRESHOLD_MODERATE: float = 65.0
    DECISION_THRESHOLD_LOW: float = 50.0

settings = Settings()

# Ensure required directories exist
for directory in [
    settings.DATA_DIR,
    settings.FIXTURES_DIR,
    settings.MEDLINEPLUS_DIR / "raw",
    settings.MEDLINEPLUS_DIR / "processed",
    settings.MEDLINEPLUS_DIR / "index",
    settings.MEDLINEPLUS_DIR / "metadata",
    settings.CACHE_DIR
]:
    directory.mkdir(parents=True, exist_ok=True)
