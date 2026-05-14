from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://saflow:saflow@localhost:5432/scrapper",
        alias="DATABASE_URL",
    )

    min_delay_s: float = Field(default=2.0, alias="MIN_DELAY_S")
    max_delay_s: float = Field(default=7.0, alias="MAX_DELAY_S")
    max_results_per_query: int = Field(default=120, alias="MAX_RESULTS_PER_QUERY")
    headless: bool = Field(default=True, alias="HEADLESS")
    http_proxy: str = Field(default="", alias="HTTP_PROXY")

    enrich_max_pages: int = Field(default=4, alias="ENRICH_MAX_PAGES")
    enrich_http_timeout: int = Field(default=15, alias="ENRICH_HTTP_TIMEOUT")
    enrich_paths: str = Field(
        default="/contact,/contact-us,/about,/about-us,/team,/imprint",
        alias="ENRICH_PATHS",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def enrich_path_list(self) -> list[str]:
        return [p.strip() for p in self.enrich_paths.split(",") if p.strip()]


settings = Settings()
