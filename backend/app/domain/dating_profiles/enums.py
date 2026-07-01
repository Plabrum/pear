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
