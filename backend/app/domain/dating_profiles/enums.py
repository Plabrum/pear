"""Dating-profile-domain enums.

Stored as TEXT via `TextEnum` (see app.utils.textenum). Member *values* match the
Postgres enum labels from the Supabase schema exactly so existing data and the
client contract stay byte-for-byte compatible.

Source migrations:
  * 20260228000000_schema.sql            — original gender/religion/interest/city/dating_status
  * 20260301000000_update_city_enum.sql  — city collapsed to Boston / New York

`dating_status` -> 'open' | 'break' | 'winging'   (public.dating_status)
`city`          -> 'Boston' | 'New York'          (public.city, post update_city_enum)
`religion`      -> full list below                (public.religion)
`interest`      -> full list below                (public.interest)
"""

from enum import Enum


class DatingStatus(Enum):
    OPEN = "open"
    BREAK = "break"
    WINGING = "winging"


class City(Enum):
    BOSTON = "Boston"
    NEW_YORK = "New York"


class Religion(Enum):
    MUSLIM = "Muslim"
    CHRISTIAN = "Christian"
    JEWISH = "Jewish"
    HINDU = "Hindu"
    BUDDHIST = "Buddhist"
    SIKH = "Sikh"
    AGNOSTIC = "Agnostic"
    ATHEIST = "Atheist"
    OTHER = "Other"
    PREFER_NOT_TO_SAY = "Prefer not to say"


class Interest(Enum):
    TRAVEL = "Travel"
    FITNESS = "Fitness"
    COOKING = "Cooking"
    MUSIC = "Music"
    ART = "Art"
    MOVIES = "Movies"
    BOOKS = "Books"
    GAMING = "Gaming"
    OUTDOORS = "Outdoors"
    SPORTS = "Sports"
    TECHNOLOGY = "Technology"
    FASHION = "Fashion"
    FOOD = "Food"
    PHOTOGRAPHY = "Photography"
    DANCE = "Dance"
    VOLUNTEERING = "Volunteering"
