"""Finite client-side budgets for anonymous public Odin data access."""

from dataclasses import dataclass
import os


def _limit(name: str, default: int, ceiling: int) -> int:
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= ceiling:
        raise ValueError(f"{name} must be an integer from 1 to {ceiling}")
    return value


@dataclass(frozen=True)
class Settings:
    max_files_per_read: int = _limit("ODIN_MAX_FILES_PER_READ", 5, 10)
    max_rows_per_read: int = _limit("ODIN_MAX_ROWS_PER_READ", 1000, 10000)
    max_columns_per_read: int = _limit("ODIN_MAX_COLUMNS_PER_READ", 20, 128)
    default_preview_rows: int = _limit("ODIN_DEFAULT_PREVIEW_ROWS", 100, 1000)
    max_list_results: int = _limit("ODIN_MAX_LIST_RESULTS", 1000, 1000)
    max_metadata_response_bytes: int = _limit("ODIN_MAX_METADATA_RESPONSE_BYTES", 2**21, 2**24)
    max_metadata_bytes: int = _limit("ODIN_MAX_METADATA_BYTES", 2**24, 2**26)
    max_file_bytes: int = _limit("ODIN_MAX_FILE_BYTES", 2**25, 2**26)
    max_download_bytes: int = _limit("ODIN_MAX_DOWNLOAD_BYTES", 2**26, 2**27)
    max_decoded_bytes: int = _limit("ODIN_MAX_DECODED_BYTES", 2**26, 2**27)
    max_output_bytes: int = _limit("ODIN_MAX_OUTPUT_BYTES", 2**20, 2**22)
    max_http_requests: int = _limit("ODIN_MAX_HTTP_REQUESTS", 32, 64)
    operation_timeout_seconds: int = _limit("ODIN_OPERATION_TIMEOUT_SECONDS", 60, 120)


SETTINGS = Settings()
PUBLIC_ORIGIN = "https://odin-smr.org"
ARCHIVE_INDEX_URL = PUBLIC_ORIGIN + "/parquet/archive/index.json"
SAMPLE_CATALOG_URL = PUBLIC_ORIGIN + "/parquet/catalog.json"
PARTITION_LEVELS = ["project", "freq_mode", "inv_mode", "product", "year", "month"]
