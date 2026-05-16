from functools import lru_cache
from urllib.parse import quote_plus, unquote_plus

from pymongo import MongoClient

from app.core.config import get_settings


def normalize_mongodb_connection_string(connection_string: str) -> str:
    if "://" not in connection_string or "@" not in connection_string:
        return connection_string

    scheme, rest = connection_string.split("://", 1)
    auth, host_and_options = rest.rsplit("@", 1)
    if ":" not in auth:
        return connection_string

    username, password = auth.split(":", 1)
    normalized_username = quote_plus(unquote_plus(username), safe="")
    normalized_password = quote_plus(unquote_plus(password), safe="")

    return f"{scheme}://{normalized_username}:{normalized_password}@{host_and_options}"


@lru_cache
def get_mongo_client() -> MongoClient:
    settings = get_settings()
    if not settings.has_documentdb_connection:
        raise RuntimeError("AZURE_DOCUMENTDB_CONNECTION_STRING is not configured.")

    return MongoClient(
        normalize_mongodb_connection_string(settings.azure_documentdb_connection_string),
        serverSelectionTimeoutMS=10000,
    )


def get_document_database():
    settings = get_settings()
    return get_mongo_client()[settings.azure_documentdb_database_name]
