# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime, timedelta, date

from dateutil.parser import (isoparse, isoparser, isointervalparser,
                             parse_interval, parse_isoduration, Interval)
from dateutil.relativedelta import relativedelta
from dateutil import tz

import pytest
import six


PARSER = isointervalparser()


def _parse(s):
    return PARSER.parse_interval(s)


#
# start / end
#
def test_start_end_basic():
    iv = _parse('2020-01-01T00:00:00Z/2020-01-02T00:00:00Z')
    assert iv.start == datetime(2020, 1, 1, tzinfo=tz.UTC)
    assert iv.end == datetime(2020, 1, 2, tzinfo=tz.UTC)
    assert iv.duration is None
    assert iv.start_open is False
    assert iv.end_open is False


def test_start_end_fractional_seconds():
    iv = _parse('2020-01-31T12:30:00.25/2020-01-31T13:00:00.75')
    assert iv.start == datetime(2020, 1, 31, 12, 30, 0, 250000)
    assert iv.end == datetime(2020, 1, 31, 13, 0, 0, 750000)
    assert iv.start_precision == 'microsecond'
    assert iv.end_precision == 'microsecond'
    assert iv.end - iv.start == timedelta(minutes=30, seconds=0,
                                          microseconds=500000)


def test_start_end_fractional_comma_separator():
    iv = _parse('2020-01-31T12:30:00,25/2020-01-31T13:00:00,75')
    assert iv.start.microsecond == 250000
    assert iv.end.microsecond == 750000


@pytest.mark.parametrize('datestr,precision', [
    ('2020', 'year'),
    ('2020-01', 'month'),
    ('2020-01-15', 'day'),
    ('20200115', 'day'),
    ('2020-W03', 'week'),
    ('2020-W03-4', 'day'),
    ('2020015', 'day'),
])
def test_endpoint_date_precision(datestr, precision):
    iv = _parse(datestr + '/2021')
    assert iv.start_precision == precision


@pytest.mark.parametrize('timestr,precision', [
    ('12', 'hour'),
    ('12:30', 'minute'),
    ('1230', 'minute'),
    ('12:30:45', 'second'),
    ('123045', 'second'),
    ('12:30:45.1', 'microsecond'),
])
def test_endpoint_time_precision(timestr, precision):
    iv = _parse('2020-01-01T' + timestr + '/2020-01-02')
    assert iv.start_precision == precision


def test_zero_length_interval_allowed():
    iv = _parse('2020-01-01/2020-01-01')
    assert iv.start == iv.end == datetime(2020, 1, 1)


#
# start / duration and duration / end, including calendar semantics
#
def test_start_duration_month_end_january_to_leap_february():
    # Adding one month to January 31st in a leap year clamps to Feb 29th.
    iv = _parse('2020-01-31/P1M')
    assert iv.start == datetime(2020, 1, 31)
    assert iv.end == datetime(2020, 2, 29)
    assert iv.duration == relativedelta(months=1)
    assert iv.end_precision is None
    assert iv.start_precision == 'day'


def test_start_duration_month_end_march():
    iv = _parse('2019-01-31/P1M')
    assert iv.end == datetime(2019, 2, 28)

    iv = _parse('2020-03-31T12:00/P1M')
    assert iv.end == datetime(2020, 4, 30, 12, 0)


def test_duration_end_month_end_backwards():
    iv = _parse('P1M/2020-02-29')
    assert iv.start == datetime(2020, 1, 29)
    assert iv.end == datetime(2020, 2, 29)


def test_duration_is_relativedelta_not_fixed_seconds():
    delta = parse_isoduration('P1Y2M3W4DT5H6M7.5S')
    assert isinstance(delta, relativedelta)
    assert delta == relativedelta(years=1, months=2, weeks=3, days=4,
                                  hours=5, minutes=6, seconds=7,
                                  microseconds=500000)


def test_start_duration_fractional_seconds():
    iv = _parse('2020-01-01T00:00:00/PT0.5S')
    assert iv.end == datetime(2020, 1, 1, 0, 0, 0, 500000)


def test_duration_end_fractional_hours():
    iv = _parse('PT0.25H/2020-01-01T00:00:00')
    assert iv.start == datetime(2019, 12, 31, 23, 45, 0)


def test_duration_preserves_endpoint_timezone():
    iv = _parse('2020-01-15T12:00:00+02:00/P1D')
    assert iv.end == datetime(2020, 1, 16, 12, 0,
                              tzinfo=tz.tzoffset(None, 2 * 3600))

    iv = _parse('P1D/2020-01-16T12:00:00+02:00')
    assert iv.start == datetime(2020, 1, 15, 12, 0,
                                tzinfo=tz.tzoffset(None, 2 * 3600))


#
# time zone offsets
#
def test_endpoints_with_different_offsets_same_instant():
    # 12:00+02:00 is the same instant as 11:00+01:00: this is not reversed.
    iv = _parse('2020-01-15T12:00:00+02:00/2020-01-15T11:30:00+01:00')
    assert iv.end - iv.start == timedelta(minutes=30)


def test_endpoints_utc_and_offset_compare_as_absolute():
    iv = _parse('2020-01-15T10:00:00Z/2020-01-15T12:00:00+02:00')
    assert iv.end - iv.start == timedelta(0)


#
# open endpoints and level indicators
#
def test_open_start():
    iv = _parse('../2020-03-01')
    assert iv.start is None
    assert iv.end == datetime(2020, 3, 1)
    assert iv.start_precision is None
    assert iv.end_precision == 'day'


def test_open_end():
    iv = _parse('2020-03-01/..')
    assert iv.start == datetime(2020, 3, 1)
    assert iv.end is None


def test_open_start_with_duration_resolves():
    iv = _parse('P1M/2020-03-01')
    assert iv.start == datetime(2020, 2, 1)
    assert iv.end == datetime(2020, 3, 1)


def test_open_end_with_duration_resolves():
    iv = _parse('2020-03-01/P1M')
    assert iv.start == datetime(2020, 3, 1)
    assert iv.end == datetime(2020, 4, 1)


def test_exclusive_boundary_level_indicators():
    iv = _parse('<2020-01-01/2020-02-01>')
    assert iv.start_open is True
    assert iv.end_open is True

    iv = _parse('2020-01-01/2020-02-01')
    assert iv.start_open is False
    assert iv.end_open is False


#
# module-level convenience functions and custom parser configuration
#
def test_module_level_parse_interval():
    iv = parse_interval('2020-01-01/P1D')
    assert iv.end == datetime(2020, 1, 2)


def test_module_level_parse_isoduration():
    assert parse_isoduration('P1D') == relativedelta(days=1)


def test_custom_separator():
    strict = isointervalparser(sep='T')
    iv = strict.parse_interval('2020-01-01T00:00/2020-01-01T12:00')
    assert iv.start == datetime(2020, 1, 1, 0, 0)
    assert iv.end == datetime(2020, 1, 1, 12, 0)

    with pytest.raises(ValueError):
        strict.parse_interval('2020-01-01 00:00/2020-01-01 12:00')


@pytest.mark.parametrize('as_bytes', [True, False])
def test_bytes_and_text_input(as_bytes):
    s = '2020-01-01/P1D'
    if as_bytes:
        s = s.encode('ascii')
    iv = PARSER.parse_interval(s)
    assert iv.end == datetime(2020, 1, 2)

    assert parse_isoduration(b'P1D' if as_bytes else 'P1D') == \
        relativedelta(days=1)


def test_interval_is_namedtuple():
    iv = _parse('2020-01-01/2020-01-02')
    assert iv == Interval(start=datetime(2020, 1, 1),
                          end=datetime(2020, 1, 2),
                          duration=None,
                          start_open=False, end_open=False,
                          start_precision='day', end_precision='day')


#
# error cases
#
@pytest.mark.parametrize('interval', [
    '2020-01-02/2020-01-01',
    '2020-01-01T12:00:00Z/2020-01-01T11:59:59Z',
    '2020-01-15T12:00:00+01:00/2020-01-15T11:00:00+01:00',
])
def test_reversed_interval_raises(interval):
    with pytest.raises(ValueError) as excinfo:
        _parse(interval)
    assert 'after the end point' in str(excinfo.value)


def test_naive_aware_mismatch_raises():
    with pytest.raises(ValueError) as excinfo:
        _parse('2020-01-01/2020-01-02T00:00:00Z')
    assert 'naive' in str(excinfo.value)

    with pytest.raises(ValueError):
        _parse('2020-01-01T00:00:00Z/2020-01-02')


@pytest.mark.parametrize('interval', [
    '2020-01-01/-P1D',
    '-P1D/2020-01-02',
    'P1D/-P1D',
])
def test_negative_duration_raises(interval):
    with pytest.raises(ValueError) as excinfo:
        _parse(interval)
    assert 'Negative durations' in str(excinfo.value)


def test_negative_duration_standalone_raises():
    with pytest.raises(ValueError) as excinfo:
        parse_isoduration('-P1D')
    assert 'Negative durations' in str(excinfo.value)


@pytest.mark.parametrize('interval', [
    '2020-01-01/2020-01-02/2020-01-03',
    '2020-01-01',
    'P1D/P2D',
    'P1D/..',
    '../P1D',
    '../..',
    '/2020-01-01',
    '2020-01-01/',
    '<P1D/2020-01-01',
    'P1D/2020-01-01<',
    '>2020-01-01/2020-01-02',
    '2020-01-01>/2020-01-02',
])
def test_malformed_interval_raises(interval):
    with pytest.raises(ValueError):
        _parse(interval)


@pytest.mark.parametrize('duration', [
    'P0.5M',           # fractional month
    'P1.5Y',           # fractional year
    'PT',              # time designator with no time component
    'P',               # no components at all
    '1D',              # missing P designator
    'PT1S2H',          # components out of order
    'P1X',             # unknown unit
])
def test_malformed_duration_raises(duration):
    with pytest.raises(ValueError):
        parse_isoduration(duration)


def test_fraction_only_allowed_on_final_component():
    with pytest.raises(ValueError) as excinfo:
        parse_isoduration('PT0.5H30M')
    assert 'final component' in str(excinfo.value)


#
# isoparse itself must continue to reject interval strings
#
@pytest.mark.parametrize('interval', [
    '2020-01-01/2020-01-02',
    '2020-01-01/P1D',
    'P1D/2020-01-02',
])
def test_isoparse_rejects_intervals(interval):
    with pytest.raises(ValueError):
        isoparse(interval)

    with pytest.raises(ValueError):
        isoparser().isoparse(interval)


def test_isoparse_still_parses_plain_datetimes():
    assert isoparse('2020-01-01T12:30:45Z') == \
        datetime(2020, 1, 1, 12, 30, 45, tzinfo=tz.UTC)
