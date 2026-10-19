from __future__ import annotations

import re
from datetime import date

MINIMUM_AGE_YEARS = 18
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MARCH = 3


class InvalidDateOfBirth(Exception):
    """Raised when a date of birth is not a real, past YYYY-MM-DD date."""


class UnderAge(Exception):
    """Raised when a valid date of birth is less than 18 years before today."""


def check_date_of_birth(text: str, today: date) -> None:
    """Accept only a past YYYY-MM-DD date at least 18 years before `today`."""
    if not _DATE_PATTERN.match(text):
        raise InvalidDateOfBirth("date of birth must be written as YYYY-MM-DD")
    try:
        birth = date.fromisoformat(text)
    except ValueError as error:
        raise InvalidDateOfBirth("date of birth is not a real calendar date") from error
    if birth > today:
        raise InvalidDateOfBirth("date of birth must not be in the future")
    if today < _eighteenth_birthday(birth):
        raise UnderAge("you must be 18 or older")


def _eighteenth_birthday(birth: date) -> date:
    try:
        return birth.replace(year=birth.year + MINIMUM_AGE_YEARS)
    except ValueError:
        return date(birth.year + MINIMUM_AGE_YEARS, _MARCH, 1)
