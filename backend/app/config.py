import os
from pathlib import Path

from pydantic_settings import BaseSettings

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    openai_api_key: str = ""

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
