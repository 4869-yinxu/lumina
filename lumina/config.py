from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LUMINA_", extra="ignore"
    )

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"

    snowluma_http_url: str = "http://snowluma:3000/"
    snowluma_ws_url: str = "ws://snowluma:3001/"
    snowluma_http_token: str = ""
    snowluma_ws_token: str = ""

    reverse_host: str = "0.0.0.0"
    reverse_port: int = 8080

    tavily_api_key: str = ""
    providers_config: str = "providers.yaml"
    admin_password: str = ""
    mcp_config: str = "mcp_servers.yaml"
    timezone: str = "Asia/Shanghai"
    ollama_url: str = "http://host.docker.internal:11434"
    embedding_model: str = "bge-m3"

    allow_risky: Annotated[list[str], NoDecode] = []
    max_steps: int = 8
    db_path: str = "data/lumina.db"

    @field_validator("allow_risky", mode="before")
    @classmethod
    def _split_allow_risky(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
