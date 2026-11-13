import itertools
from datetime import date, datetime, timedelta
import unittest

import pytest

from dateutil import tz
from dateutil.anchor import (
    CLAMP,
    FOLD_FIRST,
    FOLD_LAST,
    FOLD_RAISE,
    GAP_FIRST,
    GAP_LAST,
    GAP_RAISE,
    GAP_SKIP,
    SKIP,
    anchored_calendar,
)
from dateutil.relativedelta import SU, relativedelta


EASTERN = tz.tzrange(
    "EST", timedelta(hours=-5), "EDT", timedelta(hours=-4),
    relativedelta(hours=2, month=3, day=1, weekday=SU(2)),
    relativedelta(hours=1, month=11, day=1, weekday=SU(1)))


class AnchoredCalendarConstructionTest(unittest.TestCase):
    def test_anchor_must_be_date(self):
        with pytest.raises(TypeError):
            anchored_calendar("2023-01-31")

    def test_invalid_arguments(self):
        invalid_kwargs = [
            {"interval": 0},
            {"invalid_date": "bogus"},
            {"gap_policy": "bogus"},
            {"fold_policy": "bogus"},
        ]
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs):
                with pytest.raises(ValueError):
                    anchored_calendar(date(2023, 1, 31), **kwargs)

    def test_equality_and_hash(self):
        first = anchored_calendar(date(2023, 1, 31), interval=2)
        second = anchored_calendar(date(2023, 1, 31), interval=2)
        assert first == second
        assert hash(first) == hash(second)
        assert first != anchored_calendar(date(2023, 1, 31))
        assert first != object()


class AnchoredCalendarDateTest(unittest.TestCase):
    def test_short_month_does_not_drift_anchor(self):
        # Repeated relativedelta addition pins the series to the 28th; the
        # anchored sequence recomputes each period from January 31.
        seq = anchored_calendar(date(2023, 1, 31))
        assert seq.take(6) == [
            date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31),
            date(2023, 4, 30), date(2023, 5, 31), date(2023, 6, 30)]

    def test_leap_february_uses_the_29th(self):
        seq = anchored_calendar(date(2024, 1, 31))
        assert seq.take(4) == [
            date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31),
            date(2024, 4, 30)]

    def test_skip_omits_short_months(self):
        seq = anchored_calendar(date(2023, 1, 31), invalid_date=SKIP)
        assert [seq.get(period) for period in range(6)] == [
            date(2023, 1, 31), None, date(2023, 3, 31), None,
            date(2023, 5, 31), None]
        assert seq.take(4) == [
            date(2023, 1, 31), date(2023, 3, 31), date(2023, 5, 31),
            date(2023, 7, 31)]

    def test_skip_infers_fixed_day_anchor(self):
        seq = anchored_calendar(date(2023, 1, 31), invalid_date=SKIP)
        assert seq.month_end is False

    def test_explicit_month_end_never_skips(self):
        seq = anchored_calendar(date(2023, 1, 31), invalid_date=SKIP,
                                month_end=True)
        assert seq.take(3) == [
            date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31)]

    def test_month_end_differs_from_fixed_day_clamp(self):
        month_end = anchored_calendar(date(2023, 1, 31), month_end=True)
        fixed_day = anchored_calendar(date(2023, 1, 30), month_end=False)
        assert month_end.take(3) == [
            date(2023, 1, 31), date(2023, 2, 28), date(2023, 3, 31)]
        assert fixed_day.take(3) == [
            date(2023, 1, 30), date(2023, 2, 28), date(2023, 3, 30)]

    def test_bimonthly_interval(self):
        seq = anchored_calendar(date(2023, 1, 31), interval=2)
        assert seq.take(6) == [
            date(2023, 1, 31), date(2023, 3, 31), date(2023, 5, 31),
            date(2023, 7, 31), date(2023, 9, 30), date(2023, 11, 30)]

    def test_negative_periods(self):
        seq = anchored_calendar(date(2024, 3, 31))
        assert seq.get(-1) == date(2024, 2, 29)
        assert seq.get(-2) == date(2024, 1, 31)
        assert seq.get(-3) == date(2023, 12, 31)

    def test_negative_interval_iterates_into_the_past(self):
        seq = anchored_calendar(date(2024, 3, 31), interval=-1)
        assert seq.take(4) == [
            date(2024, 3, 31), date(2024, 2, 29), date(2024, 1, 31),
            date(2023, 12, 31)]

    def test_reversed_iteration(self):
        seq = anchored_calendar(date(2023, 1, 31))
        assert list(itertools.islice(reversed(seq), 3)) == [
            date(2023, 1, 31), date(2022, 12, 31), date(2022, 11, 30)]

    def test_reversed_negative_interval_iterates_into_the_future(self):
        seq = anchored_calendar(date(2024, 3, 31), interval=-1)
        assert list(itertools.islice(reversed(seq), 3)) == [
            date(2024, 3, 31), date(2024, 4, 30), date(2024, 5, 31)]

    def test_nth_matches_continuous_iteration(self):
        seq = anchored_calendar(date(2023, 1, 31), invalid_date=SKIP)
        materialized = seq.take(14)
        for index in (0, 1, 2, 3, 5, 8, 13):
            assert seq[index] == materialized[index]

    def test_indexing_dense_sequence_matches_get(self):
        seq = anchored_calendar(date(2023, 1, 31))
        for index in (-4, 0, 7):
            assert seq[index] == seq.get(index)

    def test_take_negative_count(self):
        seq = anchored_calendar(date(2023, 1, 31))
        assert seq.take(-2) == [date(2023, 1, 31), date(2022, 12, 31)]

    def test_slicing(self):
        seq = anchored_calendar(date(2023, 1, 31))
        assert seq[0:5:2] == [
            date(2023, 1, 31), date(2023, 3, 31), date(2023, 5, 31)]

    def test_invalid_slices(self):
        seq = anchored_calendar(date(2023, 1, 31))
        for the_slice in (slice(0, 10, 0), slice(None), slice(-1, 5),
                          slice(0, -2)):
            with self.subTest(the_slice=the_slice):
                with pytest.raises(ValueError):
                    seq[the_slice]

    def test_skip_sequence_rejects_negative_index(self):
        seq = anchored_calendar(date(2023, 1, 31), invalid_date=SKIP)
        with pytest.raises(IndexError):
            seq[-1]


class AnchoredCalendarWindowTest(unittest.TestCase):
    def test_between(self):
        seq = anchored_calendar(date(2023, 1, 31))
        assert seq.between(date(2023, 2, 1), date(2023, 5, 1)) == [
            date(2023, 2, 28), date(2023, 3, 31), date(2023, 4, 30)]

    def test_between_exclusive_bounds(self):
        seq = anchored_calendar(date(2023, 1, 31))
        assert seq.between(date(2023, 1, 31), date(2023, 4, 30),
                           inc_start=False, inc_end=False) == [
            date(2023, 2, 28), date(2023, 3, 31)]

    def test_between_reversed_window(self):
        seq = anchored_calendar(date(2023, 1, 31))
        assert seq.between(date(2023, 5, 1), date(2023, 2, 1)) == [
            date(2023, 4, 30), date(2023, 3, 31), date(2023, 2, 28)]

    def test_between_with_negative_interval(self):
        anchor = datetime(2024, 11, 3, 1, 30, tzinfo=EASTERN)
        seq = anchored_calendar(anchor, interval=-1, fold_policy=FOLD_LAST)
        result = seq.between(datetime(2024, 8, 1, tzinfo=EASTERN),
                             datetime(2024, 11, 1, tzinfo=EASTERN))
        assert [value.date() for value in result] == [
            date(2024, 10, 3), date(2024, 9, 3), date(2024, 8, 3)]

    def test_between_requires_matching_types(self):
        seq = anchored_calendar(date(2023, 1, 31))
        with pytest.raises(TypeError):
            seq.between(datetime(2023, 1, 1), date(2023, 6, 1))

        dt_seq = anchored_calendar(datetime(2023, 1, 31))
        with pytest.raises(TypeError):
            dt_seq.between(date(2023, 1, 1), date(2023, 6, 1))

        with pytest.raises(TypeError):
            seq.between("2023-01-01", date(2023, 6, 1))


class AnchoredCalendarTimeTest(unittest.TestCase):
    GAP = datetime(2024, 3, 10, 2, 30, tzinfo=EASTERN)
    FOLD = datetime(2024, 11, 3, 1, 30, tzinfo=EASTERN)

    def test_naive_datetime_keeps_wall_time(self):
        seq = anchored_calendar(datetime(2023, 1, 31, 9, 15))
        assert seq.take(3) == [
            datetime(2023, 1, 31, 9, 15),
            datetime(2023, 2, 28, 9, 15),
            datetime(2023, 3, 31, 9, 15)]

    def test_gap_raises_by_default(self):
        seq = anchored_calendar(self.GAP)
        with pytest.raises(ValueError):
            seq.get(0)

    def test_gap_first_resolves_forward(self):
        seq = anchored_calendar(self.GAP, gap_policy=GAP_FIRST,
                                fold_policy=FOLD_FIRST)
        assert seq.get(0) == datetime(2024, 3, 10, 3, 30,
                                      tzinfo=EASTERN)

    def test_gap_last_uses_post_transition_offset(self):
        seq = anchored_calendar(self.GAP, gap_policy=GAP_LAST)
        result = seq.get(0)
        assert result.replace(tzinfo=None) == datetime(2024, 3, 10, 2, 30)
        assert result.utcoffset() == timedelta(hours=-4)

    def test_gap_skip(self):
        seq = anchored_calendar(self.GAP, gap_policy=GAP_SKIP,
                                fold_policy=FOLD_FIRST)
        assert seq.get(0) is None
        assert seq[0] == datetime(2024, 4, 10, 2, 30, tzinfo=EASTERN)

    def test_gap_does_not_recur_in_a_normal_year(self):
        seq = anchored_calendar(self.GAP, gap_policy=GAP_FIRST,
                                fold_policy=FOLD_FIRST)
        assert seq.get(12).replace(tzinfo=None) == \
            datetime(2025, 3, 10, 2, 30)

    def test_fold_raises_by_default(self):
        seq = anchored_calendar(self.FOLD)
        with pytest.raises(ValueError):
            seq.get(0)

    def test_fold_first_and_last(self):
        first = anchored_calendar(self.FOLD, fold_policy=FOLD_FIRST).get(0)
        last = anchored_calendar(self.FOLD, fold_policy=FOLD_LAST).get(0)
        assert first.fold == 0
        assert first.utcoffset() == timedelta(hours=-4)
        assert last.fold == 1
        assert last.utcoffset() == timedelta(hours=-5)

    def test_explicit_raise_constants(self):
        assert GAP_RAISE == "raise"
        assert FOLD_RAISE == "raise"
        assert CLAMP == "clamp"

    def test_dst_anchor_across_a_full_year(self):
        seq = anchored_calendar(self.FOLD, gap_policy=GAP_FIRST,
                                fold_policy=FOLD_LAST)
        results = seq.take(13)
        assert results[0].fold == 1
        assert all(value.hour == 1 and value.minute == 30
                   for value in results)
        assert results[12].date() == date(2025, 11, 3)
