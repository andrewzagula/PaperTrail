import os
from pathlib import Path

from pydantic_settings import BaseSettings

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_base_url: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    local_embedding_device: str = ""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    discovery_query_model: str = "gpt-4o-mini"
    discovery_rank_model: str = "gpt-4o-mini"
    analysis_model: str = "gpt-4o-mini"
    chat_model: str = "gpt-4o-mini"
    compare_profile_model: str = "gpt-4o-mini"
    compare_synthesis_model: str = "gpt-4o"
    idea_generation_model: str = "gpt-4o-mini"
    idea_critique_model: str = "gpt-4o-mini"
    implementation_extraction_model: str = "gpt-4o-mini"
    implementation_code_model: str = "gpt-4o-mini"
    implementation_review_model: str = "gpt-4o-mini"

    data_dir: Path = DATA_DIR
    database_path: Path = DATA_DIR / "papertrail.db"
    chroma_dir: Path = DATA_DIR / "chroma"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    model_config = {
        "env_file": os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
        ),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
