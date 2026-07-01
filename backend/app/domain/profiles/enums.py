"""Profile-domain enums.

Stored as TEXT via `TextEnum` (see app.utils.textenum). Member *values* match the
Postgres enum labels from the Supabase schema exactly so existing data and the
client contract stay byte-for-byte compatible:

    gender    -> 'Male' | 'Female' | 'Non-Binary'   (public.gender)
    user_role -> 'dater' | 'winger'                  (public.user_role)
"""

from enum import Enum


class Gender(Enum):
    MALE = "Male"
    FEMALE = "Female"
    NON_BINARY = "Non-Binary"


class UserRole(Enum):
    DATER = "dater"
    WINGER = "winger"
