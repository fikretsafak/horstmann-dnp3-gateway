from enum import Enum


class UserRole(str, Enum):
    OPERATOR = "operator"
    ENGINEER = "engineer"
    INSTALLER = "installer"


class CommunicationStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
