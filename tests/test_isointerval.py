from datetime import datetime

import pytest

from dateutil import tz
from dateutil.isointerval import (
    IntervalParseError,
    isointerval,
    parse_isointerval,
)
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta


def test_start_end():
    interval = parse_isointerval("2024-02-29/2024-03-01")
    assert interval.start == datetime(2024, 2, 29)
    assert interval.end == datetime(2024, 3, 1)
    assert interval.duration == relativedelta(days=1)
    assert interval.start_precision == "day"
    assert interval.end_precision == "day"


def test_start_duration_keeps_months():
    interval = parse_isointerval("2024-01-31/P1M")
    assert interval.duration == relativedelta(months=1)
    assert interval.duration.days == 0
    assert interval.end == datetime(2024, 2, 29)


def test_duration_end_leap_year():
    interval = parse_isointerval("P1M/2024-03-29")
    assert interval.start == datetime(2024, 2, 29)
    assert interval.end == datetime(2024, 3, 29)


@pytest.mark.parametrize(
    "value",
    [
        # 2024-02-29 + P1M == 2024-03-29, so both 2024-03-30 and
        # 2024-03-31 would map back to 2024-02-29: ambiguous.
        "P1M/2024-03-31",
        "P1M/2024-03-30",
        # 2023-02-28 + P1Y == 2024-02-28, not 2024-02-29.
        "P1Y/2024-02-29",
    ],
)
def test_duration_end_ambiguous_month_end(value):
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval(value)
    assert excinfo.value.component == "interval"


def test_duration_end_unambiguous_month_end():
    interval = parse_isointerval("P1M/2024-03-29")
    assert interval.start == datetime(2024, 2, 29)
    interval = parse_isointerval("P1Y/2024-02-28")
    assert interval.start == datetime(2023, 2, 28)


def test_open_start():
    interval = parse_isointerval("../2024-03-01")
    assert interval.start is None
    assert interval.end == datetime(2024, 3, 1)
    assert interval.duration is None


def test_open_end():
    interval = parse_isointerval("2024-03-01/..")
    assert interval.start == datetime(2024, 3, 1)
    assert interval.end is None
    assert interval.duration is None


def test_open_end_with_duration():
    interval = parse_isointerval("P1M/..")
    assert interval.start is None
    assert interval.end is None
    assert interval.duration == relativedelta(months=1)


def test_open_start_with_duration():
    interval = parse_isointerval("../P1M")
    assert interval.start is None
    assert interval.end is None
    assert interval.duration == relativedelta(months=1)


def test_both_open_rejected():
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("../..")
    assert excinfo.value.component == "interval"


def test_two_durations_rejected():
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("P1M/P2M")
    assert excinfo.value.component == "interval"


@pytest.mark.parametrize(
    "value, start_precision, end_precision",
    [
        ("2024/2025", "year", "year"),
        ("2024-03/2024-05", "month", "month"),
        ("2024-03-01/2024-03-02", "day", "day"),
        ("2024-03-01T12/2024-03-01T13", "hour", "hour"),
        ("2024-03-01T12:30/2024-03-01T13:00", "minute", "minute"),
        ("2024-03-01T12:30:45/2024-03-01T12:30:46", "second", "second"),
        ("2024-03-01T12:30:45.5/2024-03-01T12:30:45.750", "fraction", "fraction"),
    ],
)
def test_precision_preserved(value, start_precision, end_precision):
    interval = parse_isointerval(value)
    assert interval.start_precision == start_precision
    assert interval.end_precision == end_precision


def test_fraction_digits_preserved():
    interval = parse_isointerval(
        "2024-03-01T12:30:45.5/2024-03-01T12:30:45.750"
    )
    assert interval.start_fraction_digits == 1
    assert interval.end_fraction_digits == 3
    assert interval.start.microsecond == 500000
    assert interval.end.microsecond == 750000


def test_reduced_precision_defaults_to_earliest():
    interval = parse_isointerval("2024/2025")
    assert interval.start == datetime(2024, 1, 1)
    assert interval.end == datetime(2025, 1, 1)

    interval = parse_isointerval("2024-03/2024-04")
    assert interval.start == datetime(2024, 3, 1)
    assert interval.end == datetime(2024, 4, 1)


@pytest.mark.parametrize(
    "value",
    ["-P1D/2024-01-02", "2024-01-01/-P1D", "+P1D/2024-01-02"],
)
def test_signed_durations_rejected(value):
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval(value)
    assert excinfo.value.component == "duration"


def test_end_before_start_rejected():
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("2024-03-01/2024-02-01")
    assert excinfo.value.component == "interval"


def test_aware_naive_mixing_rejected():
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("2024-01-01T00:00:00Z/2024-01-02T00:00:00")
    assert excinfo.value.component == "interval"

    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("2024-01-01T00:00:00/2024-01-02T00:00:00Z")
    assert excinfo.value.component == "interval"


def test_cross_offset_duration():
    interval = parse_isointerval(
        "2024-03-01T00:00:00+08:00/2024-03-01T00:00:00-05:00"
    )
    assert interval.duration == relativedelta(hours=13)
    assert interval.start.utcoffset().total_seconds() == 8 * 3600
    assert interval.end.utcoffset().total_seconds() == -5 * 3600


def test_cross_offset_end_before_start():
    # Wall-clock end is later, but the instant it denotes is earlier.
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("2024-01-01T12:00:00Z/2024-01-01T13:00:00+08:00")
    assert excinfo.value.component == "interval"


def test_fractional_seconds_duration():
    interval = parse_isointerval("2024-01-01T00:00:00/PT0.25S")
    assert interval.duration == relativedelta(microseconds=250000)
    assert interval.end == datetime(2024, 1, 1, 0, 0, 0, 250000)
    assert interval.end_precision == "fraction"

    interval = parse_isointerval("PT0.5S/2024-01-01T00:00:00.5")
    assert interval.start == datetime(2024, 1, 1)


@pytest.mark.parametrize(
    "value",
    [
        "2024-01-01/P1.5Y",
        "2024-01-01/P1.5M",
        "2024-01-01/P1.5W",
        "2024-01-01/P1.5D",
        "2024-01-01/PT1.5H",
        "2024-01-01/PT1.5M",
    ],
)
def test_imprecise_fractional_units_rejected(value):
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval(value)
    assert excinfo.value.component == "duration"


def test_too_many_fraction_digits_rejected():
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("2024-01-01T00:00:00.1234567/2024-01-02")
    assert excinfo.value.component == "start"

    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval("2024-01-01/PT0.1234567S")
    assert excinfo.value.component == "duration"


@pytest.mark.parametrize(
    "value, component",
    [
        ("2024-13-01/2025-01-01", "start"),
        ("2024-02-30/2025-01-01", "start"),
        ("2024-01-01/2024-13-01", "end"),
        ("2024-01-01/P1Q", "duration"),
        ("2024-01-01/P", "duration"),
        ("2024-01-01/PT", "duration"),
        ("2024-01-01", "interval"),
        ("2024-01-01/2024-01-02/2024-01-03", "interval"),
        ("2024-W09-1/2024-03-01", "start"),
        ("2024-060/2024-03-01", "start"),
        ("/2024-03-01", "start"),
        ("2024-03-01/", "end"),
    ],
)
def test_error_identifies_component(value, component):
    with pytest.raises(IntervalParseError) as excinfo:
        parse_isointerval(value)
    assert excinfo.value.component == component


def test_non_string_rejected():
    with pytest.raises(TypeError):
        parse_isointerval(b"2024-01-01/2024-01-02")


@pytest.mark.parametrize(
    "value",
    [
        "2024-02-29/2024-03-01",
        "2024-01-31/P1M",
        "P1M/2024-03-29",
        "2024/2025",
        "2024-03/2024-05",
        "2024-03-01T12/2024-03-01T13",
        "2024-03-01T12:30/2024-03-01T13:00",
        "2024-03-01T12:30:45.123456/2024-03-01T13:00:00.5",
        "2024-03-01T00:00:00+08:00/2024-03-01T00:00:00-05:00",
        "2024-01-01T00:00:00Z/PT0.25S",
        "P1Y2M3DT4H5M6.5S/2025-03-04T04:05:06.5",
        "../2024-03-01",
        "2024-03-01/..",
        "../P1M",
        "P1M/..",
    ],
)
def test_roundtrip(value):
    interval = parse_isointerval(value)
    reparsed = parse_isointerval(interval.to_iso())
    assert reparsed == interval
    assert reparsed.to_iso() == interval.to_iso()


@pytest.mark.parametrize(
    "value, canonical",
    [
        # relativedelta normalizes components at construction, and the
        # canonical encoding reflects that.
        ("PT90H/2024-01-05T18:00:00", "P3DT18H/2024-01-05T18:00:00"),
        ("P1W/2024-01-08", "P7D/2024-01-08"),
        ("2024-01-01/P14M", "2024-01-01/P1Y2M"),
        ("2024-01-01/PT24H", "2024-01-01/P1D"),
        ("2024-01-01/PT0.50S", "2024-01-01/PT0.5S"),
        ("2024-01-01/PT0.0S", "2024-01-01/P0D"),
        ("2024-01-01T00:00:00,5/2024-01-01T00:00:01", 
         "2024-01-01T00:00:00.5/2024-01-01T00:00:01"),
        ("20240301/20240302", "2024-03-01/2024-03-02"),
        ("2024-01-01T00:00:00+00:00/2024-01-02T00:00:00Z",
         "2024-01-01T00:00:00Z/2024-01-02T00:00:00Z"),
    ],
)
def test_canonical_encoding(value, canonical):
    assert parse_isointerval(value).to_iso() == canonical


def test_equality_across_forms():
    assert parse_isointerval("2024-01-01/P1D") == parse_isointerval(
        "2024-01-01/2024-01-02"
    )
    # 2024-01-31 + P1M == 2024-02-29, so the two forms denote the same
    # interval.
    assert parse_isointerval("2024-01-31/P1M") == parse_isointerval(
        "2024-01-31/2024-02-29"
    )
    # A calendar month is not a fixed number of days.
    assert parse_isointerval("2024-01-01/P1M") != parse_isointerval(
        "2024-01-01/2024-01-31"
    )


def test_equality_ignores_offset_representation():
    assert parse_isointerval(
        "2024-01-01T08:00:00+08:00/.."
    ) == parse_isointerval("2024-01-01T00:00:00Z/..")


def test_str_and_repr():
    interval = parse_isointerval("2024-01-31/P1M")
    assert str(interval) == "2024-01-31/P1M"
    assert repr(interval) == "isointerval('2024-01-31/P1M')"


def test_isoparse_still_rejects_intervals():
    with pytest.raises(ValueError):
        isoparse("2024-01-01/2024-01-02")


def test_result_types():
    interval = parse_isointerval("2024-01-01/2024-01-02")
    assert isinstance(interval, isointerval)
    assert isinstance(interval.duration, relativedelta)


def test_aware_interval_utc_offset():
    interval = parse_isointerval("2024-01-01T00:00:00Z/2024-01-02T00:00:00Z")
    assert interval.start.tzinfo == tz.UTC
    assert interval.duration == relativedelta(days=1)
