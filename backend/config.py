"""Central, environment-driven configuration for the RAG service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "YouTube RAG API"
    environment: str = "development"
    log_level: str = "INFO"

    hf_token: SecretStr | None = Field(default=None, validation_alias="HF_TOKEN")
    hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    hf_llm_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    embedding_timeout_seconds: int = Field(default=45, validation_alias="RAG_EMBEDDING_TIMEOUT_SECONDS", ge=5, le=180)
    llm_max_new_tokens: int = 500
    llm_timeout_seconds: int = 45

    pinecone_api_key: SecretStr | None = Field(default=None, validation_alias="PINECONE_API_KEY")
    pinecone_index: str = "youtube-rag"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_namespace: str = "youtube-transcripts"
    pinecone_ready_timeout_seconds: int = Field(default=90, ge=10, le=300)

    langsmith_api_key: SecretStr | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    langsmith_tracing: bool = False
    langsmith_project: str = "youtube-rag"

    chunk_size: int = Field(default=850, validation_alias="RAG_CHUNK_SIZE", ge=200, le=4000)
    chunk_overlap: int = Field(default=150, validation_alias="RAG_CHUNK_OVERLAP", ge=0, le=1000)
    retrieval_candidates: int = Field(default=18, validation_alias="RAG_RETRIEVAL_CANDIDATES", ge=4, le=50)
    final_context_chunks: int = Field(default=5, validation_alias="RAG_FINAL_CONTEXT_CHUNKS", ge=1, le=12)
    max_context_chars: int = Field(default=8500, validation_alias="RAG_MAX_CONTEXT_CHARS", ge=1000, le=30000)
    transcript_cache_dir: Path = Field(default=Path(".cache/transcripts"), validation_alias="RAG_TRANSCRIPT_CACHE_DIR")
    transcript_retries: int = Field(default=2, ge=0, le=5)
    reranker_mode: str = Field(default="lexical", validation_alias="RAG_RERANKER_MODE")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="RAG_CORS_ORIGINS")

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_must_fit_chunk(cls, overlap: int, info) -> int:
        chunk_size = info.data.get("chunk_size", 850)
        if overlap >= chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
        return overlap

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Parse the human-friendly comma-separated CORS setting after dotenv loading."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return one immutable configuration object per process."""

    return Settings()
