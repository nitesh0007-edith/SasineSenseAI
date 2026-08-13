from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./data/uploads")
    render_dir: Path = Path("./data/rendered")
    derived_dir: Path = Path("./data/derived")
    review_log_dir: Path = Path("./data/derived/reviews")

    max_upload_mb: int = 25
    pdf_render_dpi: int = 150

    ocr_provider: str = "mock"
    ner_provider: str = "spacy"
    structured_extraction_provider: str = "mock"

    # Preprocessing (Phase 2). Preprocessing is opt-in and never mutates the
    # original render; a derived image is produced alongside metadata.
    preprocess_enabled: bool = False
    preprocess_grayscale: bool = True
    preprocess_normalize_contrast: bool = True
    preprocess_deskew: bool = True
    preprocess_denoise: bool = True
    preprocess_threshold: bool = False

    # Place resolution (Phase 9).
    gazetteer_csv: Path = Path("./data/gazetteer/sample_scotland_places.csv")

    # Real structured-extraction provider (Task 7.3). Mesh API is an
    # OpenAI-compatible gateway (https://api.meshapi.ai/v1). The key is read from
    # the environment (MESH_API_KEY / STRUCTURED_API_KEY) and never hard-coded.
    structured_api_base: str = "https://api.meshapi.ai/v1"
    structured_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("structured_api_key", "mesh_api_key"),
    )
    structured_api_model: str = "anthropic/claude-sonnet-5"
    structured_api_timeout: int = 90

    # Persistence. Defaults to a local SQLite file (zero-setup); point at a
    # Postgres/PostGIS DSN to use a server, e.g.
    # postgresql+psycopg://postgres:postgres@localhost:5432/ros_ai
    database_url: str = "sqlite:///./data/derived/app.db"

    review_high_confidence: float = 0.90
    review_medium_confidence: float = 0.70

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

for path in (
    settings.data_dir,
    settings.upload_dir,
    settings.render_dir,
    settings.derived_dir,
    settings.review_log_dir,
):
    path.mkdir(parents=True, exist_ok=True)
