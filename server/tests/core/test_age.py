from datetime import date

import pytest

from image_edit_server.core.age import InvalidDateOfBirth, UnderAge, check_date_of_birth

TODAY = date(2026, 2, 28)


def test_exactly_18_today_passes():
    check_date_of_birth("2008-02-28", TODAY)


def test_one_day_short_is_under_age():
    with pytest.raises(UnderAge):
        check_date_of_birth("2008-03-01", TODAY)


def test_leap_day_birth_is_under_age_on_28_february():
    with pytest.raises(UnderAge):
        check_date_of_birth("2008-02-29", date(2026, 2, 28))


def test_leap_day_birth_passes_on_1_march():
    check_date_of_birth("2008-02-29", date(2026, 3, 1))


@pytest.mark.parametrize(
    "text", ["2008-13-01", "08/05/2001", "2008-1-1", "2001-05-08T00:00:00", "", "2001-02-30"]
)
def test_malformed_dates_are_invalid(text):
    with pytest.raises(InvalidDateOfBirth):
        check_date_of_birth(text, TODAY)


def test_tomorrow_is_invalid():
    with pytest.raises(InvalidDateOfBirth):
        check_date_of_birth("2026-03-01", TODAY)


def test_today_is_under_age_not_invalid():
    with pytest.raises(UnderAge):
        check_date_of_birth("2026-02-28", TODAY)
