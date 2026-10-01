# -*- coding: utf-8 -*-
"""Tests for dateutil.workcalendar.WorkCalendar."""
from datetime import date, datetime, time, timedelta

import pytest

from dateutil import tz
from dateutil.workcalendar import WorkCalendar

NYC = tz.gettz("America/New_York")
UTC = tz.UTC

HOUR = 3600.0

# 2021-03-08 is a Monday; the week containing the US spring forward.
MON = date(2021, 3, 8)
TUE = date(2021, 3, 9)
WED = date(2021, 3, 10)
FRI = date(2021, 3, 12)
SAT = date(2021, 3, 13)
SPRING_FORWARD = date(2021, 3, 14)  # Sunday, 02:00 -> 03:00 in NYC

FALL_BACK = date(2021, 11, 7)       # Sunday, 02:00 -> 01:00 in NYC


def local(day, hour, minute=0, second=0):
    return datetime.combine(day, time(hour, minute, second), tzinfo=NYC)


@pytest.fixture
def lunch_cal():
    """Mon-Fri 09:00-12:00 and 13:00-17:00, with a lunch break."""
    return WorkCalendar(NYC, weekly={
        d: [(time(9), time(12)), (time(13), time(17))]
        for d in range(5)
    })


@pytest.fixture
def night_cal():
    """Mon-Fri overnight shifts 22:00 -> 06:00 the next morning."""
    return WorkCalendar(NYC, weekly={
        d: [(time(22), time(6))] for d in range(5)
    })


# ----------------------------------------------------------------------
# basic accumulation: lunch breaks and weekends
# ----------------------------------------------------------------------
def test_work_between_full_day_with_lunch(lunch_cal):
    assert lunch_cal.work_between(local(MON, 9), local(MON, 17)) == 7 * HOUR


def test_work_between_lunch_break_counts_nothing(lunch_cal):
    assert lunch_cal.work_between(local(MON, 12), local(MON, 13)) == 0.0
    assert lunch_cal.work_between(
        local(MON, 11, 30), local(MON, 13, 30)) == 1 * HOUR


def test_work_between_skips_weekend(lunch_cal):
    next_mon = FRI + timedelta(3)
    assert lunch_cal.work_between(local(FRI, 17), local(next_mon, 9)) == 0.0
    assert lunch_cal.work_between(
        local(FRI, 16), local(next_mon, 10)) == 2 * HOUR


def test_work_between_reversed_is_zero(lunch_cal):
    assert lunch_cal.work_between(local(MON, 17), local(MON, 9)) == 0.0
    assert lunch_cal.work_between(local(MON, 9), local(MON, 9)) == 0.0


def test_work_between_naive_datetimes_use_calendar_tz(lunch_cal):
    assert lunch_cal.work_between(
        datetime(2021, 3, 8, 9), datetime(2021, 3, 8, 17)) == 7 * HOUR


# ----------------------------------------------------------------------
# overnight (cross-midnight) shifts
# ----------------------------------------------------------------------
def test_night_shift_crosses_midnight(night_cal):
    assert night_cal.work_between(
        local(MON, 22), local(TUE, 6)) == 8 * HOUR


def test_night_shift_tail_belongs_to_previous_day(night_cal):
    # Tuesday has no shift start of its own before 22:00; the early
    # morning hours are the tail of Monday's shift.
    assert night_cal.work_between(local(TUE, 5), local(TUE, 7)) == 1 * HOUR
    assert night_cal.work_between(local(MON, 21), local(MON, 22)) == 0.0


def test_overnight_overlap_with_next_day_not_double_counted():
    cal = WorkCalendar(NYC, weekly={
        0: [(time(22), time(6))],   # Monday night into Tuesday
        1: [(time(0), time(6))],    # Tuesday early morning overlaps it
    })
    assert cal.work_between(local(TUE, 0), local(TUE, 6)) == 6 * HOUR
    assert cal.work_between(local(MON, 22), local(TUE, 6)) == 8 * HOUR


def test_overlapping_spans_same_day_merged():
    cal = WorkCalendar(NYC, weekly={
        0: [(time(9), time(12)), (time(11), time(14))],
    })
    assert cal.work_between(local(MON, 9), local(MON, 14)) == 5 * HOUR


def test_full_day_shift_midnight_to_midnight():
    cal = WorkCalendar(NYC, weekly={2: [(time(0), time(0))]})
    assert cal.work_between(local(WED, 0), local(WED + timedelta(1), 0)) \
        == 24 * HOUR


# ----------------------------------------------------------------------
# per-date overrides: holidays and temporary overtime
# ----------------------------------------------------------------------
def test_holiday_override_removes_work(lunch_cal):
    cal = WorkCalendar(NYC, weekly=lunch_cal._weekly,
                       overrides={MON: None})
    assert cal.work_between(local(MON, 9), local(MON, 17)) == 0.0
    # The following Monday still uses the weekly template.
    assert cal.work_between(
        local(MON + timedelta(7), 9), local(MON + timedelta(7), 17)) \
        == 7 * HOUR


def test_overtime_override_adds_weekend_work(lunch_cal):
    cal = WorkCalendar(NYC, weekly=lunch_cal._weekly,
                       overrides={SAT: [(time(10), time(14))]})
    assert cal.work_between(local(SAT, 9), local(SAT, 15)) == 4 * HOUR


def test_override_replaces_weekly_template():
    cal = WorkCalendar(
        NYC,
        weekly={5: [(time(9), time(17))]},          # Saturdays 9-17
        overrides={SAT: [(time(10), time(12))]},    # except this one
    )
    assert cal.work_between(local(SAT, 9), local(SAT, 17)) == 2 * HOUR


def test_overnight_override_shift():
    cal = WorkCalendar(NYC, overrides={FRI: [(time(22), time(6))]})
    assert cal.work_between(local(FRI, 21), local(SAT, 7)) == 8 * HOUR


# ----------------------------------------------------------------------
# DST transitions (America/New_York, 2021)
# ----------------------------------------------------------------------
def test_spring_forward_night_shift_loses_one_real_hour():
    # Saturday night 22:00 EST -> Sunday 06:00 EDT spans the 02:00
    # spring forward, so the 8 wall hours pass in 7 real hours.
    cal = WorkCalendar(NYC, weekly={5: [(time(22), time(6))]})
    assert cal.work_between(
        local(SAT, 22), local(SPRING_FORWARD, 6)) == 7 * HOUR


def test_spring_forward_gap_shift_contributes_nothing():
    # 02:00-03:00 does not exist on 2021-03-14 in NYC.
    cal = WorkCalendar(NYC, overrides={
        SPRING_FORWARD: [(time(2), time(3))],
    })
    assert cal.work_between(
        local(SPRING_FORWARD, 0), local(SPRING_FORWARD, 6)) == 0.0


def test_spring_forward_imaginary_endpoint_falls_forward():
    # An endpoint inside the gap is read as the first real moment
    # (03:00 EDT), so 01:00 -> 02:00 lasts one real hour and
    # 02:00 -> 04:00 lasts one real hour.
    cal = WorkCalendar(NYC, overrides={
        SPRING_FORWARD: [(time(1), time(2))],
    })
    assert cal.work_between(
        local(SPRING_FORWARD, 0), local(SPRING_FORWARD, 6)) == 1 * HOUR
    cal = WorkCalendar(NYC, overrides={
        SPRING_FORWARD: [(time(2), time(4))],
    })
    assert cal.work_between(
        local(SPRING_FORWARD, 0), local(SPRING_FORWARD, 6)) == 1 * HOUR


def test_spring_forward_week_total():
    # Nightly 22:00 -> 06:00 shifts, Sunday 2021-03-07 through
    # Saturday 2021-03-13; the Saturday night shift crosses the spring
    # forward and lasts only 7 real hours.
    cal = WorkCalendar(NYC, weekly={d: [(time(22), time(6))]
                                    for d in range(7)})
    assert cal.work_between(
        local(date(2021, 3, 7), 22), local(SPRING_FORWARD, 6)) == 55 * HOUR


def test_fall_back_day_counts_repeated_hour_as_real_time():
    cal = WorkCalendar(NYC, weekly={6: [(time(0), time(4))]})
    # 00:00 EDT -> 04:00 EST spans 5 real hours.
    assert cal.work_between(
        local(FALL_BACK, 0), local(FALL_BACK, 4)) == 5 * HOUR


def test_fall_back_ambiguous_endpoint_uses_first_occurrence():
    cal = WorkCalendar(NYC, overrides={FALL_BACK: [(time(0), time(1))]})
    # Wall 01:00 is ambiguous; fold=0 picks the first (EDT) occurrence,
    # so the shift lasts exactly one real hour.
    assert cal.work_between(local(FALL_BACK, 0), local(FALL_BACK, 6)) \
        == 1 * HOUR


def test_fall_back_week_total():
    # Nightly 22:00 -> 06:00 shifts, Sunday 2021-10-31 through
    # Saturday 2021-11-06; the Saturday night shift crosses the fall
    # back and lasts 9 real hours.
    cal = WorkCalendar(NYC, weekly={d: [(time(22), time(6))]
                                    for d in range(7)})
    assert cal.work_between(
        local(date(2021, 10, 31), 22), local(FALL_BACK, 6)) == 57 * HOUR


# ----------------------------------------------------------------------
# add_work: forward and backward displacement
# ----------------------------------------------------------------------
def test_add_work_forward_across_lunch(lunch_cal):
    assert lunch_cal.add_work(local(MON, 11, 30), 1 * HOUR) \
        == local(MON, 13, 30)


def test_add_work_forward_across_weekend(lunch_cal):
    assert lunch_cal.add_work(local(FRI, 16), 2 * HOUR) \
        == local(FRI + timedelta(3), 10)


def test_add_work_backward_across_lunch(lunch_cal):
    assert lunch_cal.add_work(local(MON, 13, 30), -1 * HOUR) \
        == local(MON, 11, 30)


def test_add_work_backward_across_weekend(lunch_cal):
    assert lunch_cal.add_work(local(MON, 9), -1 * HOUR) \
        == local(MON - timedelta(3), 16)


def test_add_work_zero_returns_input_unchanged(lunch_cal):
    dt = local(MON, 11, 30)
    assert lunch_cal.add_work(dt, 0) is dt
    assert lunch_cal.add_work(dt, timedelta(0)) is dt


def test_add_work_accepts_timedelta(lunch_cal):
    assert lunch_cal.add_work(local(MON, 9), timedelta(hours=1)) \
        == local(MON, 10)


def test_add_work_lands_exactly_on_shift_boundary(lunch_cal):
    # 3 working hours from 09:00 end exactly at the 12:00 lunch edge.
    assert lunch_cal.add_work(local(MON, 9), 3 * HOUR) == local(MON, 12)
    # Half an hour more continues after lunch.
    assert lunch_cal.add_work(local(MON, 9), 3.5 * HOUR) \
        == local(MON, 13, 30)


def test_add_work_from_exact_shift_end(lunch_cal):
    # 12:00 is not a working moment (half-open intervals): forward
    # displacement resumes at 13:00, backward displacement counts into
    # the morning shift that just ended.
    assert lunch_cal.add_work(local(MON, 12), 1 * HOUR) == local(MON, 14)
    assert lunch_cal.add_work(local(MON, 12), -1 * HOUR) == local(MON, 11)


def test_add_work_night_shift_across_midnight(night_cal):
    assert night_cal.add_work(local(MON, 23), 7 * HOUR) == local(TUE, 6)
    assert night_cal.add_work(local(TUE, 6), -7 * HOUR) == local(MON, 23)


def test_add_work_across_spring_forward():
    cal = WorkCalendar(NYC, weekly={5: [(time(22), time(6))]})
    result = cal.add_work(local(SAT, 22), 7 * HOUR)
    assert result == local(SPRING_FORWARD, 6)
    assert result.utcoffset() == timedelta(hours=-4)  # EDT after the jump


def test_add_work_across_fall_back():
    cal = WorkCalendar(NYC, weekly={6: [(time(0), time(4))]})
    result = cal.add_work(local(FALL_BACK, 0), 5 * HOUR)
    assert result == local(FALL_BACK, 4)
    assert result.utcoffset() == timedelta(hours=-5)  # EST after fallback


def test_add_work_roundtrip_through_dst_week():
    # Nightly shifts; the 20 working hours from Saturday 2021-03-13
    # 23:00 cross the spring forward on Sunday 02:00.
    cal = WorkCalendar(NYC, weekly={d: [(time(22), time(6))]
                                    for d in range(7)})
    start = local(SAT, 23)
    seconds = 20 * HOUR
    end = cal.add_work(start, seconds)
    assert cal.work_between(start, end) == pytest.approx(seconds)
    assert cal.add_work(end, -seconds) == start


def test_add_work_from_idle_moment_starts_at_next_shift(lunch_cal):
    # Forward displacement from a non-working moment begins counting at
    # the next shift start, so the exact round trip back lands on that
    # shift start rather than on the original idle moment.
    next_mon = SAT + timedelta(2)
    end = lunch_cal.add_work(local(SAT, 12), 1 * HOUR)
    assert end == local(next_mon, 10)
    assert lunch_cal.add_work(end, -1 * HOUR) == local(next_mon, 9)


def test_add_work_without_any_work_raises():
    cal = WorkCalendar(NYC)
    with pytest.raises(ValueError):
        cal.add_work(local(MON, 9), 1 * HOUR)


# ----------------------------------------------------------------------
# boundary semantics of is_working
# ----------------------------------------------------------------------
def test_is_working_boundaries(lunch_cal):
    assert lunch_cal.is_working(local(MON, 9))
    assert not lunch_cal.is_working(local(MON, 12))
    assert lunch_cal.is_working(local(MON, 13))
    assert not lunch_cal.is_working(local(MON, 17))
    assert not lunch_cal.is_working(local(SAT, 10))


def test_is_working_night_shift(night_cal):
    assert night_cal.is_working(local(MON, 23))
    assert night_cal.is_working(local(TUE, 5))
    assert not night_cal.is_working(local(TUE, 6))
    assert not night_cal.is_working(local(TUE, 12))


# ----------------------------------------------------------------------
# construction and validation
# ----------------------------------------------------------------------
def test_timezone_accepted_as_string():
    cal = WorkCalendar("America/New_York",
                       weekly={0: [(time(9), time(17))]})
    assert cal.work_between(local(MON, 9), local(MON, 17)) == 8 * HOUR


def test_invalid_weekday_rejected():
    with pytest.raises(ValueError):
        WorkCalendar(NYC, weekly={7: [(time(9), time(17))]})


def test_invalid_span_rejected():
    with pytest.raises(TypeError):
        WorkCalendar(NYC, weekly={0: [(9, 17)]})
    with pytest.raises(ValueError):
        WorkCalendar(NYC, weekly={0: [(time(9),)]})
    with pytest.raises(ValueError):
        WorkCalendar(NYC, weekly={
            0: [(time(9, tzinfo=UTC), time(17))],
        })


def test_aware_input_in_other_timezone(lunch_cal):
    start = local(MON, 9).astimezone(UTC)
    end = local(MON, 17).astimezone(UTC)
    assert lunch_cal.work_between(start, end) == 7 * HOUR
