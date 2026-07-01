from enum import Enum


class Gender(Enum):
    MALE = "Male"
    FEMALE = "Female"
    NON_BINARY = "Non-Binary"


class UserRole(Enum):
    DATER = "dater"
    WINGER = "winger"
