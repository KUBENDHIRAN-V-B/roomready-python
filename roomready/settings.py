from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOM_TYPES = ("Standard", "Deluxe", "Suite")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./roomready.db"
    inspection_required_for: str = "Standard,Deluxe,Suite"  # which room types need a second pair of eyes
    stall_after_minutes: int = 60  # GET /settings reports it; no rule here reads it
    seed_dir: str = "seed"
    host: str = "0.0.0.0"  # bind every interface; the ready log line prints it
    port: int = 8080

    @field_validator("inspection_required_for")
    @classmethod
    def _known_types(cls, value: str) -> str:
        unknown = [t for t in cls.split_types(value) if t not in ROOM_TYPES]
        if unknown:
            raise ValueError(f"INSPECTION_REQUIRED_FOR names unknown room type(s) {unknown}; choose from {', '.join(ROOM_TYPES)}")
        return value

    @staticmethod
    def split_types(value: str) -> list[str]:
        return [t.strip() for t in value.split(",") if t.strip()]

    @property
    def inspection_types(self) -> list[str]:
        return self.split_types(self.inspection_required_for)

    def needs_inspection(self, room_type: str) -> bool:
        return room_type in self.inspection_types
