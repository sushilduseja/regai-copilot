from pydantic_settings import BaseSettings
from pydantic import model_validator


class ProductionConfigError(ValueError):
    pass


class Settings(BaseSettings):
    environment: str = "development"
    app_base_url: str = "http://localhost:8000"
    log_level: str = "info"
    secret_key: str = "change-me"
    data_dir: str = "./data"
    database_url: str = "sqlite:///data/regai.db"

    workos_client_id: str = ""
    workos_api_key: str = ""
    workos_redirect_uri: str = "http://localhost:8000/auth/callback"
    bootstrap_admin_emails: str = ""

    pinecone_api_key: str = ""
    pinecone_index_name: str = "regai-mvp"

    nvidia_embedding_model: str = "nvidia/llama-3.2-nv-embedqa-1b-v2"

    groq_api_key: str = ""
    nvidia_api_key: str = ""
    default_llm_provider: str = "groq"

    max_upload_size: int = 52428800
    upload_warn_disk_usage_percent: int = 80

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment != "production":
            return self

        missing = []
        if not self.workos_client_id:
            missing.append("WORKOS_CLIENT_ID")
        if not self.workos_api_key:
            missing.append("WORKOS_API_KEY")
        if not self.workos_redirect_uri or self.workos_redirect_uri.startswith("http://"):
            missing.append("WORKOS_REDIRECT_URI (must be https)")
        if not self.pinecone_api_key:
            missing.append("PINECONE_API_KEY")
        if not self.secret_key or self.secret_key == "change-me" or len(self.secret_key) < 32:
            missing.append("SECRET_KEY (min 32 chars)")
        if not self.groq_api_key and not self.nvidia_api_key:
            missing.append("GROQ_API_KEY or NVIDIA_API_KEY")

        if self.default_llm_provider == "groq" and not self.groq_api_key:
            missing.append("GROQ_API_KEY (matches DEFAULT_LLM_PROVIDER)")
        if self.default_llm_provider == "nvidia" and not self.nvidia_api_key:
            missing.append("NVIDIA_API_KEY (matches DEFAULT_LLM_PROVIDER)")

        if not self.database_url.startswith("sqlite:///") or "/data/" not in self.database_url:
            missing.append("DATABASE_URL must point to persistent disk in production")

        if missing:
            raise ProductionConfigError(
                f"Production requires: {', '.join(missing)}"
            )

        return self
