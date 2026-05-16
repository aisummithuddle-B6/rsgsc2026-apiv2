from dataclasses import dataclass
from functools import lru_cache
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = getenv("APP_NAME", "Insurance RMIS API")
    api_v1_prefix: str = getenv("API_V1_PREFIX", "/api/v1")

    azure_documentdb_connection_string: str = getenv(
        "AZURE_DOCUMENTDB_CONNECTION_STRING",
        "mongodb+srv://mktweb:Dmitri111!!!@rsg2026.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000",
    )
    azure_documentdb_database_name: str = getenv(
        "AZURE_DOCUMENTDB_DATABASE_NAME",
        "rsg2026",
    )

    @property
    def has_documentdb_connection(self) -> bool:
        return bool(self.azure_documentdb_connection_string.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
