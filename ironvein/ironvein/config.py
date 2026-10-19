from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    telegram_api_url: str = ""  # свой Bot API сервер (Local Bot API); пусто — api.telegram.org
    database_url: str = "postgresql+asyncpg://ironvein:ironvein@localhost:5432/ironvein"
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    environment: str = "development"

    game_speed: float = 1.0
    starter_crowns: int = 1000
    market_fee_bps: int = 200
    contract_fee_bps: int = 200
    company_fee: int = 500
    warehouse_capacity: int = 2000
    deposit_scale_players: int = 100  # регенерация × max(1, активные за сутки / N); 0 — без масштабирования
    job_poll_seconds: float = 5.0
    premium_reservation_minutes: int = 30

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v):
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, int):
            return [v]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
