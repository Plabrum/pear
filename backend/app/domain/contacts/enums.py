"""Contacts-domain enums.

Stored as TEXT via `TextEnum` (see app.utils.textenum). Member *values* match the
Postgres `public.wingperson_status` enum labels exactly:

    wingperson_status -> 'invited' | 'active' | 'removed'
"""

from enum import Enum


class WingpersonStatus(Enum):
    INVITED = "invited"
    ACTIVE = "active"
    REMOVED = "removed"
