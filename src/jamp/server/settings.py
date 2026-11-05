"""Environment-backed settings for the JAMP server."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    api_key_hash_secret: str
    audit_path: str


settings = Settings(
    database_url=os.getenv("JAMP_DATABASE_URL", ""),
    redis_url=os.getenv("JAMP_REDIS_URL", ""),
    api_key_hash_secret=os.getenv("JAMP_API_KEY_HASH_SECRET", ""),
    audit_path=os.getenv(
        "JAMP_AUDIT_PATH",
        "/tmp/jamp/audit/provenance_traces.jsonl",
    ),
)
