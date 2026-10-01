# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from datetime import date, datetime, time

import pytest

from dateutil import tz
from dateutil.workcalendar import WorkCalendar

UTC = tz.UTC
NYC = tz.gettz("America/New_York")

HOUR = 3600.0

# 2026-01-05 is a Monday; 2026-03-08 and 2026-11-01 are the Sundays of
# the America/New_York DST transitions (spring forward / fall back).
MON = date(2026, 1, 5)
SPRING_FORWARD = date(2026, 3, 8)
FALL_BACK = date(2026, 11, 1)


def naive(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute))


def office_cal():
    """Mon-Fri 09:00-17:00, UTC."""
    return WorkCalendar(
        UTC, {d: [(time(9), time(17))] for d in range(5)})


def lunch_cal():
    """Mon-Fri 09:00-12:00 and 13:00-17:00, UTC (one-hour lunch)."""
    return WorkCalendar(
        UTC,
        {d: [(time(9), time(12)), (time(13), time(17))]
         for d in range(5)})


class TestWorkSecondsBetween:
    def test_full_day(self):
        cal = office_cal()
        assert cal.work_seconds_between(
            naive(MON, 9), naive(MON, 17)) == 8 * HOUR

    def test_clips_to_work_hours(self):
        cal = office_cal()
        assert cal.work_seconds_between(
            naive(MON, 6), naive(MON, 23)) == 8 * HOUR

    def test_lunch_break_excluded(self):
        cal = lunch_cal()
        assert cal.work_seconds_between(
            naive(MON, 8), naive(MON, 18)) == 7 * HOUR

    def test_weekend_excluded(self):
        cal = office_cal()
        friday = date(2026, 1, 9)
        monday = date(2026, 1, 12)
        assert cal.work_seconds_between(
            naive(friday, 9), naive(monday, 17)) == 16 * HOUR

    def test_zero_duration(self):
        cal = office_cal()
        assert cal.work_seconds_between(
            naive(MON, 10), naive(MON, 10)) == 0.0
        # Also zero outside work time.
        assert cal.work_seconds_between(
            naive(MON, 3), naive(MON, 3)) == 0.0

    def test_reversed_is_negative(self):
        cal = office_cal()
        forward = cal.work_seconds_between(naive(MON, 9), naive(MON, 17))
        assert cal.work_seconds_between(
            naive(MON, 17), naive(MON, 9)) == -forward

    def test_microseconds(self):
        cal = office_cal()
        start = datetime(2026, 1, 5, 9, 0, 0, 500000)
        end = datetime(2026, 1, 5, 9, 0, 2, 500000)
        assert cal.work_seconds_between(start, end) == 2.0

    def test_aware_inputs(self):
        cal = WorkCalendar(
            NYC, {d: [(time(9), time(17))] for d in range(5)})
        # 09:00-17:00 EST is 14:00-22:00 UTC.
        start = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
        end = datetime(2026, 1, 5, 22, 0, tzinfo=UTC)
        assert cal.work_seconds_between(start, end) == 8 * HOUR


class TestNightShift:
    """Overnight interval 22:00-06:00 declared on Mondays, UTC."""

    def night_cal(self):
        return WorkCalendar(UTC, {0: [(time(22), time(6))]})

    def test_cross_midnight_duration(self):
        cal = self.night_cal()
        tue = date(2026, 1, 6)
        assert cal.work_seconds_between(
            naive(MON, 21), naive(tue, 7)) == 8 * HOUR

    def test_add_forward_across_midnight(self):
        cal = self.night_cal()
        assert cal.add_work_seconds(naive(MON, 23), 4 * HOUR) == \
            naive(date(2026, 1, 6), 3)

    def test_add_backward_across_midnight(self):
        cal = self.night_cal()
        assert cal.add_work_seconds(
            naive(date(2026, 1, 6), 3), -4 * HOUR) == naive(MON, 23)

    def test_spillover_merges_with_next_day(self):
        # Monday night shift spills into Tuesday 06:00 and overlaps the
        # Tuesday 05:00-12:00 interval; the union is 22:00 -> 12:00.
        cal = WorkCalendar(UTC, {
            0: [(time(22), time(6))],
            1: [(time(5), time(12))],
        })
        tue = date(2026, 1, 6)
        assert cal.work_seconds_between(
            naive(MON, 20), naive(tue, 13)) == 14 * HOUR
        # Landing exactly on the merged interval's end.
        assert cal.add_work_seconds(naive(MON, 21), 14 * HOUR) == \
            naive(tue, 12)


class TestBoundaries:
    def test_add_lands_exactly_on_close(self):
        cal = office_cal()
        assert cal.add_work_seconds(naive(MON, 9), 8 * HOUR) == \
            naive(MON, 17)

    def test_start_exactly_at_close_is_not_work(self):
        cal = office_cal()
        tue = date(2026, 1, 6)
        assert cal.add_work_seconds(naive(MON, 17), HOUR) == \
            naive(tue, 10)
        assert cal.work_seconds_between(naive(MON, 17), naive(tue, 9)) \
            == 0.0

    def test_backward_from_open_boundary(self):
        cal = office_cal()
        tue = date(2026, 1, 6)
        assert cal.add_work_seconds(naive(tue, 9), -HOUR) == \
            naive(MON, 16)

    def test_backward_lands_on_open_boundary(self):
        cal = office_cal()
        assert cal.add_work_seconds(naive(MON, 17), -8 * HOUR) == \
            naive(MON, 9)

    def test_lunch_boundaries(self):
        cal = lunch_cal()
        # 12:00 is the start of lunch (not work); 13:00 is work again.
        assert cal.add_work_seconds(naive(MON, 12), HOUR) == \
            naive(MON, 14)
        assert cal.add_work_seconds(naive(MON, 13), -HOUR) == \
            naive(MON, 11)


class TestZeroSeconds:
    def test_add_zero_inside_work(self):
        cal = office_cal()
        dt = naive(MON, 10)
        assert cal.add_work_seconds(dt, 0) == dt

    def test_add_zero_outside_work(self):
        cal = office_cal()
        dt = naive(MON, 3)
        assert cal.add_work_seconds(dt, 0) == dt

    def test_add_zero_on_weekend(self):
        cal = office_cal()
        dt = naive(date(2026, 1, 10), 12)  # Saturday
        assert cal.add_work_seconds(dt, 0) == dt


class TestOverlappingIntervals:
    def test_overlap_counted_once(self):
        cal = WorkCalendar(
            UTC, {0: [(time(9), time(13)), (time(12), time(17))]})
        tue = date(2026, 1, 6)
        assert cal.work_seconds_between(
            naive(MON, 0), naive(tue, 0)) == 8 * HOUR

    def test_touching_intervals_are_continuous(self):
        cal = WorkCalendar(
            UTC, {0: [(time(9), time(12)), (time(12), time(15))]})
        assert cal.add_work_seconds(naive(MON, 11), 2 * HOUR) == \
            naive(MON, 13)


class TestOverrides:
    def test_holiday_replaces_schedule(self):
        cal = WorkCalendar(
            UTC,
            {d: [(time(9), time(17))] for d in range(5)},
            overrides={MON: []},
        )
        tue = date(2026, 1, 6)
        assert cal.work_seconds_between(naive(MON, 0), naive(tue, 0)) \
            == 0.0
        # Friday 16:00 + 2 work hours skips the Monday holiday.
        friday = date(2026, 1, 2)
        assert cal.add_work_seconds(naive(friday, 16), 2 * HOUR) == \
            naive(tue, 10)

    def test_weekend_overtime(self):
        saturday = date(2026, 1, 10)
        cal = WorkCalendar(
            UTC,
            {d: [(time(9), time(17))] for d in range(5)},
            overrides={saturday: [(time(10), time(14))]},
        )
        sunday = date(2026, 1, 11)
        assert cal.work_seconds_between(
            naive(saturday, 0), naive(sunday, 0)) == 4 * HOUR
        friday = date(2026, 1, 9)
        assert cal.add_work_seconds(
            naive(friday, 16, 30), 2 * HOUR) == naive(saturday, 11, 30)

    def test_override_replaces_not_extends(self):
        cal = WorkCalendar(
            UTC,
            {d: [(time(9), time(17))] for d in range(5)},
            overrides={MON: [(time(9), time(10))]},
        )
        tue = date(2026, 1, 6)
        assert cal.work_seconds_between(naive(MON, 0), naive(tue, 0)) \
            == HOUR


class TestDST:
    """America/New_York transitions: 2026-03-08 spring forward (02:00
    -> 03:00, one missing hour), 2026-11-01 fall back (02:00 -> 01:00,
    one repeated hour).  Durations are real elapsed seconds."""

    def daily_cal(self):
        """Every day 00:00-08:00 local, NYC."""
        return WorkCalendar(
            NYC, {d: [(time(0), time(8))] for d in range(7)})

    def test_spring_forward_day_is_shorter(self):
        cal = self.daily_cal()
        assert cal.work_seconds_between(
            naive(SPRING_FORWARD, 0), naive(SPRING_FORWARD, 8)) \
            == 7 * HOUR

    def test_spring_forward_add_within_day(self):
        cal = self.daily_cal()
        assert cal.add_work_seconds(
            naive(SPRING_FORWARD, 0), 7 * HOUR) == \
            naive(SPRING_FORWARD, 8)

    def test_spring_forward_add_spills_to_monday(self):
        cal = self.daily_cal()
        monday = date(2026, 3, 9)
        assert cal.add_work_seconds(
            naive(SPRING_FORWARD, 0), 8 * HOUR) == naive(monday, 1)

    def test_spring_forward_backward(self):
        cal = self.daily_cal()
        monday = date(2026, 3, 9)
        assert cal.add_work_seconds(
            naive(monday, 1), -8 * HOUR) == naive(SPRING_FORWARD, 0)

    def test_fall_back_day_is_longer(self):
        cal = self.daily_cal()
        assert cal.work_seconds_between(
            naive(FALL_BACK, 0), naive(FALL_BACK, 8)) == 9 * HOUR

    def test_fall_back_add_within_day(self):
        cal = self.daily_cal()
        assert cal.add_work_seconds(
            naive(FALL_BACK, 0), 9 * HOUR) == naive(FALL_BACK, 8)

    def test_fall_back_backward(self):
        cal = self.daily_cal()
        assert cal.add_work_seconds(
            naive(FALL_BACK, 8), -9 * HOUR) == naive(FALL_BACK, 0)

    def test_night_shift_over_spring_forward(self):
        # Saturday 22:00 -> Sunday 06:00 across the missing hour: the
        # shift really lasts 7 hours.
        cal = WorkCalendar(NYC, {5: [(time(22), time(6))]})
        saturday = date(2026, 3, 7)
        assert cal.work_seconds_between(
            naive(saturday, 22), naive(SPRING_FORWARD, 6)) == 7 * HOUR
        assert cal.add_work_seconds(
            naive(saturday, 23), 5 * HOUR) == naive(SPRING_FORWARD, 5)
        assert cal.add_work_seconds(
            naive(SPRING_FORWARD, 5), -5 * HOUR) == naive(saturday, 23)

    def test_night_shift_over_fall_back(self):
        # Saturday 22:00 -> Sunday 06:00 across the repeated hour: the
        # shift really lasts 9 hours.
        cal = WorkCalendar(NYC, {5: [(time(22), time(6))]})
        saturday = date(2026, 10, 31)
        assert cal.work_seconds_between(
            naive(saturday, 22), naive(FALL_BACK, 6)) == 9 * HOUR

    def test_repeated_hour_uses_first_occurrence(self):
        # Sunday 00:30-01:30 on fall-back day: 01:30 is ambiguous and
        # resolves to its first occurrence, so the interval is one
        # real hour.
        cal = WorkCalendar(NYC, {6: [(time(0, 30), time(1, 30))]})
        assert cal.work_seconds_between(
            naive(FALL_BACK, 0), naive(FALL_BACK, 3)) == HOUR

    def test_imaginary_end_resolved_forward(self):
        # Saturday 22:00 -> Sunday 02:30, but 02:30 does not exist on
        # spring-forward day; it resolves forward to 03:30 EDT, so the
        # shift is 4.5 real hours.
        cal = WorkCalendar(NYC, {5: [(time(22), time(2, 30))]})
        saturday = date(2026, 3, 7)
        assert cal.work_seconds_between(
            naive(saturday, 20), naive(SPRING_FORWARD, 8)) == 4.5 * HOUR


class TestAwareness:
    def test_naive_in_naive_out(self):
        cal = office_cal()
        result = cal.add_work_seconds(datetime(2026, 1, 5, 9), HOUR)
        assert result == datetime(2026, 1, 5, 10)
        assert result.tzinfo is None

    def test_aware_in_same_tz_out(self):
        cal = WorkCalendar(
            NYC, {d: [(time(9), time(17))] for d in range(5)})
        start = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)  # 09:00 EST
        result = cal.add_work_seconds(start, HOUR)
        assert result == datetime(2026, 1, 5, 15, 0, tzinfo=UTC)
        assert result.tzinfo is UTC

    def test_naive_interpreted_in_calendar_zone(self):
        cal = WorkCalendar(
            NYC, {d: [(time(9), time(17))] for d in range(5)})
        assert cal.work_seconds_between(
            datetime(2026, 1, 5, 9), datetime(2026, 1, 5, 17)) \
            == 8 * HOUR


class TestRoundTrip:
    def test_add_then_subtract_over_lunch(self):
        cal = lunch_cal()
        dt = naive(MON, 10, 30)
        seconds = 5.5 * HOUR
        assert cal.add_work_seconds(
            cal.add_work_seconds(dt, seconds), -seconds) == dt

    def test_add_then_subtract_across_dst(self):
        cal = WorkCalendar(
            NYC, {d: [(time(0), time(8))] for d in range(7)})
        dt = naive(date(2026, 3, 6), 4)  # Friday, inside work time
        seconds = 20 * HOUR
        assert cal.add_work_seconds(
            cal.add_work_seconds(dt, seconds), -seconds) == dt


class TestValidation:
    def test_equal_start_end_rejected(self):
        with pytest.raises(ValueError):
            WorkCalendar(UTC, {0: [(time(9), time(9))]})

    def test_bad_weekday_rejected(self):
        with pytest.raises(ValueError):
            WorkCalendar(UTC, {7: [(time(9), time(17))]})

    def test_aware_time_rejected(self):
        with pytest.raises(ValueError):
            WorkCalendar(UTC, {0: [(time(9, tzinfo=UTC), time(17))]})

    def test_datetime_override_key_rejected(self):
        with pytest.raises(TypeError):
            WorkCalendar(UTC, {}, overrides={
                datetime(2026, 1, 5, 9): []})

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_unknown_zone_rejected(self):
        with pytest.raises(ValueError):
            WorkCalendar("Not/AZone", {})

    def test_zone_name_accepted(self):
        cal = WorkCalendar("UTC", {0: [(time(9), time(17))]})
        assert cal.timezone is not None

    def test_no_work_time_forward(self):
        cal = WorkCalendar(UTC, {})
        with pytest.raises(ValueError):
            cal.add_work_seconds(naive(MON, 9), HOUR)

    def test_no_work_time_backward(self):
        cal = WorkCalendar(UTC, {})
        with pytest.raises(ValueError):
            cal.add_work_seconds(naive(MON, 9), -HOUR)

    def test_overrides_exhausted(self):
        cal = WorkCalendar(
            UTC, {}, overrides={MON: [(time(9), time(17))]})
        with pytest.raises(ValueError):
            cal.add_work_seconds(naive(MON, 16), 2 * HOUR)
