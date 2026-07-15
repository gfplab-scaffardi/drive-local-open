from __future__ import annotations


class DriveLocalOpenError(Exception):
    """User-facing failure with a stable scenario code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


# Scenario codes from the public plan
S1_NOT_DRIVE_URL = "S1"
S2_DRIVE_NOT_MOUNTED = "S2"
S3_AMBIGUOUS_ACCOUNT = "S3"
S4_NOT_SYNCED = "S4"
S5_SHARED_SHORTCUT = "S5"
S6_FILE_PARENT = "S6"
S7_MY_DRIVE = "S7"
S8_TOMBSTONE = "S8"
S9_DB_ERROR = "S9"
S10_PATH_NORMALIZE = "S10"
S11_TIMEOUT = "S11"
S12_NO_URL = "S12"
S13_PROTOCOL = "S13"
S14_OFFLINE_OK = "S14"
