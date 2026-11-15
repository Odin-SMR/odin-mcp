from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    bucket: str = os.getenv("ODIN_BUCKET", "odin-level2")
    aws_profile: str = os.getenv("ODIN_AWS_PROFILE", "odin")
    max_files_per_read: int = int(os.getenv("ODIN_MAX_FILES_PER_READ", "5"))
    max_rows_per_read: int = int(os.getenv("ODIN_MAX_ROWS_PER_READ", "1000"))
    max_columns_per_read: int = int(os.getenv("ODIN_MAX_COLUMNS_PER_READ", "20"))
    default_preview_rows: int = int(os.getenv("ODIN_DEFAULT_PREVIEW_ROWS", "100"))
    max_list_results: int = int(os.getenv("ODIN_MAX_LIST_RESULTS", "1000"))


SETTINGS = Settings()

PARTITION_LEVELS = ["project", "freq_mode", "inv_mode", "product", "year", "month"]
