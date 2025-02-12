from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

class ListenEventType(Enum):
    ON_AUDIT_LOG_ENTRY = "auditlogentry"
class FilterType(Enum):
    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"
