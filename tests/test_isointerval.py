# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime

from dateutil import tz
from dateutil.parser import (isoparse, isointervalparse, isointervalparser,
                             ISOInterval)

import pytest


@pytest.mark.parametrize('interval_str, start, end, precision', [
    # start/end
    ('2017-01-01/2017-02-01',
     datetime(2017, 1, 1), datetime(2017, 2, 1), 'day'),
    # start/duration
    ('2017-01-01/P1M2D',
     datetime(2017, 1, 1), datetime(2017, 2, 3), 'day'),
    # duration/end
    ('P1M2D/2017-02-03',
     datetime(2017, 1, 1), datetime(2017, 2, 3), 'day'),
    # weeks are exactly 7 days
    ('2017-01-01/P2W',
     datetime(2017, 1, 1), datetime(2017, 1, 15), 'day'),
    # time components in durations
    ('2017-01-01T00:00:00/PT12H30M',
     datetime(2017, 1, 1, 0, 0), datetime(2017, 1, 1, 12, 30), 'second'),
    # fractional seconds, comma or dot separator
    ('2017-01-01T00:00:00.5/2017-01-01T00:00:01.25',
     datetime(2017, 1, 1, 0, 0, 0, 500000),
     datetime(2017, 1, 1, 0, 0, 1, 250000), 'microsecond'),
    ('2017-01-01T00:00:00/PT0.5S',
     datetime(2017, 1, 1, 0, 0),
     datetime(2017, 1, 1, 0, 0, 0, 500000), 'second'),
    ('2017-01-01T00:00:00/PT0,5S',
     datetime(2017, 1, 1, 0, 0),
     datetime(2017, 1, 1, 0, 0, 0, 500000), 'second'),
    # months keep their calendar meaning (not a fixed number of seconds):
    # January 31st plus one month clamps to the end of February
    ('2017-01-31/P1M',
     datetime(2017, 1, 31), datetime(2017, 2, 28), 'day'),
    # ... and to February 29th in a leap year
    ('2016-01-31/P1M',
     datetime(2016, 1, 31), datetime(2016, 2, 29), 'day'),
    # crossing a month boundary with a day-based duration
    ('2017-01-30/P5D',
     datetime(2017, 1, 30), datetime(2017, 2, 4), 'day'),
    # endpoints with different time zone offsets
    ('2017-03-01T00:00:00+08:00/2017-03-01T12:00:00-05:00',
     datetime(2017, 3, 1, 0, 0, tzinfo=tz.tzoffset(None, 8 * 3600)),
     datetime(2017, 3, 1, 12, 0, tzinfo=tz.tzoffset(None, -5 * 3600)),
     'second'),
    # a duration anchored to an aware endpoint stays aware
    ('2017-03-01T00:00:00+08:00/PT6H',
     datetime(2017, 3, 1, 0, 0, tzinfo=tz.tzoffset(None, 8 * 3600)),
     datetime(2017, 3, 1, 6, 0, tzinfo=tz.tzoffset(None, 8 * 3600)),
     'second'),
    # a zero-length interval is valid
    ('2017-01-01/2017-01-01',
     datetime(2017, 1, 1), datetime(2017, 1, 1), 'day'),
])
def test_isointerval(interval_str, start, end, precision):
    interval = isointervalparse(interval_str)

    assert interval.start == start
    assert interval.end == end
    assert not interval.start_open
    assert not interval.end_open
    assert interval.precision == precision


@pytest.mark.parametrize('interval_str, start_open, end_open, bound', [
    ('2017-01-01/', False, True, datetime(2017, 1, 1)),
    ('2017-01-01/..', False, True, datetime(2017, 1, 1)),
    ('/2017-01-01', True, False, datetime(2017, 1, 1)),
    ('../2017-01-01', True, False, datetime(2017, 1, 1)),
])
def test_isointerval_open_end(interval_str, start_open, end_open, bound):
    interval = isointervalparse(interval_str)

    assert interval.start_open == start_open
    assert interval.end_open == end_open

    if start_open:
        assert interval.start is None
        assert interval.end == bound
    else:
        assert interval.start == bound
        assert interval.end is None


@pytest.mark.parametrize('interval_str, precision', [
    ('2017/2018', 'year'),
    ('2017-01/2017-03', 'month'),
    ('20170101/2017-01-02', 'day'),
    ('2017-01-01T12/2017-01-01T13', 'hour'),
    ('2017-01-01T12:30/2017-01-01T12:45', 'minute'),
    ('2017-01-01T12:30:15/2017-01-01T12:30:45', 'second'),
    ('2017-01-01T12:30:15.5/2017-01-01T12:30:15.75', 'microsecond'),
    # with endpoints of differing precision, the coarser one wins
    ('2017/2018-01-01T00:00:00.5', 'year'),
    ('2017-01/2017-03-01', 'month'),
    # the precision comes from the datetime anchoring the duration
    ('2017-01-01T12:30/PT1H', 'minute'),
    ('PT1H/2017-01-01T12:30', 'minute'),
])
def test_isointerval_precision(interval_str, precision):
    assert isointervalparse(interval_str).precision == precision


@pytest.mark.parametrize('interval_str', [
    # end before start
    '2017-02-01/2017-01-01',
    # end before start once time zone offsets are accounted for
    '2017-03-01T00:00:00-05:00/2017-03-01T00:00:00+08:00',
])
def test_isointerval_reversed(interval_str):
    with pytest.raises(ValueError):
        isointervalparse(interval_str)


@pytest.mark.parametrize('interval_str', [
    # one endpoint aware, the other naive
    '2017-01-01T00:00:00Z/2017-01-02T00:00:00',
    '2017-01-01T00:00:00/2017-01-02T00:00:00+05:00',
])
def test_isointerval_inconsistent_tzinfo(interval_str):
    with pytest.raises(ValueError):
        isointervalparse(interval_str)


@pytest.mark.parametrize('interval_str', [
    '2017-01-01/-P1D',
    '-P1D/2017-01-02',
    '2017-01-01/-PT0.5S',
])
def test_isointerval_negative_duration(interval_str):
    with pytest.raises(ValueError):
        isointervalparse(interval_str)


@pytest.mark.parametrize('interval_str', [
    '',                     # not an interval at all
    '2017-01-01',           # a bare datetime is not an interval
    '/',                    # both ends open
    '../..',                # both ends open
    'P1D/P2D',              # two durations
    'P1D/..',               # unanchored duration
    '../P1D',               # unanchored duration
    '2017-01-01/P',         # duration with no components
    '2017-01-01/PT',        # duration with no components
    '2017-01-01/P1.5Y',     # fractional years are ambiguous
    '2017-01-01/P1.5M',     # fractional months are ambiguous
    '2017-01-01/2017-02-01/2017-03-01',  # too many components
    '2017-01-01/not-a-date',
])
def test_isointerval_invalid(interval_str):
    with pytest.raises(ValueError):
        isointervalparse(interval_str)


def test_isointerval_equality():
    interval1 = isointervalparse('2017-01-01/2017-02-01')
    interval2 = isointervalparse('2017-01-01/P31D')

    assert interval1 == interval2
    assert not interval1 != interval2
    assert interval1 != '2017-01-01/2017-02-01'


def test_isointerval_repr():
    interval = isointervalparse('2017-01-01/2017-02-01')

    assert repr(interval) == (
        "ISOInterval(start=datetime.datetime(2017, 1, 1, 0, 0), "
        "end=datetime.datetime(2017, 2, 1, 0, 0), "
        "start_open=False, end_open=False, precision='day')")


def test_isointervalparser_sep():
    parser = isointervalparser(sep='T')

    interval = parser.parse_isointerval('2017-01-01T00:00:00/PT1H')
    assert interval.end == datetime(2017, 1, 1, 1, 0)

    with pytest.raises(ValueError):
        parser.parse_isointerval('2017-01-01 00:00:00/PT1H')


def test_isointerval_stream():
    import io

    interval = isointervalparse(io.StringIO('2017-01-01/2017-02-01'))

    assert interval.start == datetime(2017, 1, 1)
    assert interval.end == datetime(2017, 2, 1)


@pytest.mark.parametrize('interval_str', [
    '2017-01-01/2017-02-01',
    '2017-01-01/P1M',
    'P1M/2017-02-01',
    '2017-01-01/..',
])
def test_isoparse_does_not_accept_intervals(interval_str):
    # The plain ISO-8601 datetime parser must keep rejecting intervals
    with pytest.raises(ValueError):
        isoparse(interval_str)


def test_isoparse_still_parses_datetimes():
    assert isoparse('2017-01-01T12:30:15.5') == \
        datetime(2017, 1, 1, 12, 30, 15, 500000)
