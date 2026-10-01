# -*- coding: utf-8 -*-
"""
This module offers a parser for ISO-8601 time interval strings.

It supports the three interval representations allowed by ISO-8601:

- Start and end:        ``2020-01-01T00:00:00Z/2020-01-02T00:00:00Z``
- Start and duration:   ``2020-01-01T00:00:00Z/P1D``
- Duration and end:     ``P1D/2020-01-02T00:00:00Z``

An endpoint may be left explicitly open (unbounded) using ``..``, and an
endpoint may be marked as an exclusive ("open") interval boundary using the
level indicators ``<`` (start) and ``>`` (end), e.g.
``<2020-01-01/2020-02-01>``.

Durations are returned as :class:`dateutil.relativedelta.relativedelta`
objects rather than :class:`datetime.timedelta`, because months (and years)
do not represent a fixed number of seconds.  Adding or subtracting a
duration therefore uses the established calendar semantics of
:class:`dateutil.relativedelta.relativedelta`, including month-end clamping
(e.g. ``2020-01-31/P1M`` ends on ``2020-02-29``).

.. versionadded:: 2.10.0
"""
from datetime import timedelta
from collections import namedtuple
import re

from dateutil.relativedelta import relativedelta

from .isoparser import isoparser, _takes_ascii

__all__ = ["Interval", "isointervalparser",
           "parse_interval", "parse_isoduration"]


#: Result of :meth:`isointervalparser.parse_interval`.
#:
#: ``start`` and ``end`` are :class:`datetime.datetime` instances or
#: ``None`` when an endpoint is explicitly open (``..``).  ``duration`` is
#: the :class:`~dateutil.relativedelta.relativedelta` parsed from the string,
#: or ``None`` when both endpoints are given.  ``start_open`` and
#: ``end_open`` are ``True`` when the corresponding boundary is exclusive
#: (marked with ``<`` or ``>``).  ``start_precision`` and
#: ``end_precision`` describe the granularity of the endpoint as it appeared
#: in the input (one of ``year``, ``month``, ``week``, ``day``, ``hour``,
#: ``minute``, ``second`` or ``microsecond``); they are ``None`` for
#: computed and open endpoints.
Interval = namedtuple("Interval",
                      ["start", "end", "duration",
                       "start_open", "end_open",
                       "start_precision", "end_precision"])


class isointervalparser(isoparser):
    """
    A parser for ISO-8601 time interval strings.

    :param sep:
        A single character that separates date and time portions in the
        interval endpoints, forwarded to :class:`isoparser`.  If ``None``,
        any single non-digit character is accepted; pass ``'T'`` for strict
        ISO-8601 adherence.
    """
    _OPEN_ENDPOINT = b'..'
    _DURATION_UNITS = (('years', None),
                       ('months', None),
                       ('weeks', 604800),
                       ('days', 86400),
                       ('hours', 3600),
                       ('minutes', 60),
                       ('seconds', 1))

    _DURATION_REGEX = re.compile(
        b'^P'
        b'(?:(?P<years>[0-9]+(?:[\\.,][0-9]+)?)Y)?'
        b'(?:(?P<months>[0-9]+(?:[\\.,][0-9]+)?)M)?'
        b'(?:(?P<weeks>[0-9]+(?:[\\.,][0-9]+)?)W)?'
        b'(?:(?P<days>[0-9]+(?:[\\.,][0-9]+)?)D)?'
        b'(?:T'
        b'(?:(?P<hours>[0-9]+(?:[\\.,][0-9]+)?)H)?'
        b'(?:(?P<minutes>[0-9]+(?:[\\.,][0-9]+)?)M)?'
        b'(?:(?P<seconds>[0-9]+(?:[\\.,][0-9]+)?)S)?'
        b')?$')

    @_takes_ascii
    def parse_interval(self, interval_str):
        """
        Parse an ISO-8601 time interval string into an :class:`Interval`.

        The two components of the interval are separated by ``/``.  Each
        component is either an ISO-8601 datetime (parseable by
        :meth:`isoparser.isoparse`), an ISO-8601 duration or the open
        endpoint marker ``..``.  At least one component must be a datetime.

        Examples::

            >>> p = isointervalparser()
            >>> p.parse_interval('2020-01-31/P1M').end
            datetime.datetime(2020, 2, 29, 0, 0)
            >>> interval = p.parse_interval(
            ...     '2020-01-15T12:00:00+02:00/2020-01-15T11:30:00+01:00')
            >>> interval.end - interval.start
            datetime.timedelta(seconds=1800)

        :param interval_str:
            A string or stream containing a single ISO-8601 interval.

        :return:
            An :class:`Interval` describing the endpoints, boundary flags,
            duration and input precision.

        :raises ValueError:
            Raised for malformed intervals, reversed intervals, mixtures of
            naive and time-zone-aware endpoints and negative durations.
        """
        components = interval_str.split(b'/')
        if len(components) != 2:
            raise ValueError('Interval string must contain exactly one "/": '
                             '{!r}'.format(interval_str.decode('ascii')))

        start, start_open, start_precision, start_is_duration = \
            self._parse_start(components[0])
        end, end_open, end_precision, end_is_duration = \
            self._parse_end(components[1])

        if start_is_duration and end_is_duration:
            raise ValueError('Interval cannot be expressed as two '
                             'durations: {!r}'.format(
                                 interval_str.decode('ascii')))
        elif start_is_duration:
            if end is None:
                raise ValueError('An interval with a duration but no end '
                                 'point cannot be resolved: {!r}'.format(
                                     interval_str.decode('ascii')))
            duration = start
            start = end - duration
            start_precision = None
        elif end_is_duration:
            if start is None:
                raise ValueError('An interval with a duration but no start '
                                 'point cannot be resolved: {!r}'.format(
                                     interval_str.decode('ascii')))
            duration = end
            end = start + duration
            end_precision = None
        else:
            duration = None
            self._check_endpoints(start, end, interval_str)

        if start is None and end is None:
            raise ValueError('An interval with neither a start point nor an '
                             'end point is not defined: {!r}'.format(
                                 interval_str.decode('ascii')))

        return Interval(start=start, end=end, duration=duration,
                        start_open=start_open, end_open=end_open,
                        start_precision=start_precision,
                        end_precision=end_precision)

    def _parse_start(self, token):
        if token == self._OPEN_ENDPOINT:
            return None, False, None, False

        boundary_open = False
        if token[:1] == b'<':
            boundary_open = True
            token = token[1:]

        if not token or token == self._OPEN_ENDPOINT:
            raise ValueError('Invalid start component: {!r}'.format(
                token.decode('ascii')))

        if token[:1] == b'P' or token[:2] in (b'+P', b'-P'):
            if boundary_open:
                raise ValueError('The "<" level indicator applies to a '
                                 'datetime start point, not a duration')
            return self.parse_isoduration(token), False, None, True

        if token[-1:] == b'>':
            raise ValueError('The ">" level indicator may only be used on '
                             'the end point of an interval')

        dt = self.isoparse(token)
        return dt, boundary_open, self._endpoint_precision(token), False

    def _parse_end(self, token):
        if token == self._OPEN_ENDPOINT:
            return None, False, None, False

        boundary_open = False
        if token[:1] == b'<':
            raise ValueError('The "<" level indicator may only be used on '
                             'the start point of an interval')

        if token[-1:] == b'>':
            boundary_open = True
            token = token[:-1]

        if not token or token == self._OPEN_ENDPOINT:
            raise ValueError('Invalid end component: {!r}'.format(
                token.decode('ascii')))

        if token[:1] == b'P' or token[:2] in (b'+P', b'-P'):
            if boundary_open:
                raise ValueError('The ">" level indicator applies to a '
                                 'datetime end point, not a duration')
            return self.parse_isoduration(token), False, None, True

        dt = self.isoparse(token)
        return dt, boundary_open, self._endpoint_precision(token), False

    def _check_endpoints(self, start, end, interval_str):
        if start is None or end is None:
            return

        if (start.tzinfo is None) != (end.tzinfo is None):
            raise ValueError('Cannot combine a naive endpoint with a '
                             'time-zone-aware endpoint: {!r}'.format(
                                 interval_str.decode('ascii')))

        if start > end:
            raise ValueError('Interval start point is after the end point: '
                             '{!r}'.format(interval_str.decode('ascii')))

    @_takes_ascii
    def parse_isoduration(self, duration_str):
        """
        Parse an ISO-8601 duration string into a
        :class:`dateutil.relativedelta.relativedelta`.

        Years, months and weeks are kept on the :class:`relativedelta`;
        they are never converted into a fixed number of seconds.  Negative
        durations are not supported.  A fractional value is only allowed on
        the final component of the duration, and fractional years or months
        are rejected because they do not correspond to a fixed duration.

        :param duration_str:
            A string or stream containing a single ISO-8601 duration, such
            as ``P1Y2M3DT4H5M6.5S``.

        :return:
            Returns a :class:`~dateutil.relativedelta.relativedelta`.
        """
        if duration_str[:1] == b'-':
            raise ValueError('Negative durations are not supported: '
                             '{!r}'.format(duration_str.decode('ascii')))

        if duration_str[:1] == b'+':
            duration_str = duration_str[1:]

        if duration_str[:1] != b'P':
            raise ValueError('Invalid ISO-8601 duration: {!r}'.format(
                duration_str.decode('ascii')))

        match = self._DURATION_REGEX.match(duration_str)
        if match is None:
            raise ValueError('Invalid ISO-8601 duration: {!r}'.format(
                duration_str.decode('ascii')))

        present = [(name, unit_seconds, match.group(name))
                   for name, unit_seconds in self._DURATION_UNITS
                   if match.group(name) is not None]

        if not present:
            raise ValueError('Duration contains no date or time '
                             'components: {!r}'.format(
                                 duration_str.decode('ascii')))

        time_designator = b'T' in duration_str
        if time_designator and not any(name in ('hours', 'minutes', 'seconds')
                                       for name, _, _ in present):
            raise ValueError('Time designator "T" is not followed by a time '
                             'component: {!r}'.format(
                                 duration_str.decode('ascii')))

        for index, (name, _, value) in enumerate(present):
            is_fractional = b'.' in value or b',' in value
            if not is_fractional:
                continue

            if name in ('years', 'months'):
                raise ValueError(
                    'A fractional {unit!r} does not represent a fixed '
                    'duration; use a smaller unit: {duration!r}'.format(
                        unit=name,
                        duration=duration_str.decode('ascii')))

            if index != len(present) - 1:
                raise ValueError('Only the final component of a duration '
                                 'may be fractional: {!r}'.format(
                                     duration_str.decode('ascii')))

        integer_parts = {}
        fraction_delta = timedelta()
        for name, unit_seconds, value in present:
            if b'.' in value or b',' in value:
                whole, fraction = re.split(b'[\\.,]', value, 1)
                if unit_seconds is not None:
                    # Exact conversion truncated to microseconds.
                    fraction_us = (int(fraction) * unit_seconds *
                                   10 ** 6 // 10 ** len(fraction))
                    fraction_delta += timedelta(microseconds=fraction_us)
                integer_parts[name] = int(whole)
            else:
                integer_parts[name] = int(value)

        return relativedelta(**integer_parts) + fraction_delta

    def _endpoint_precision(self, token):
        _, date_end = self._parse_isodate(token)

        if date_end >= len(token):
            return self._date_precision(token)

        time_part = token[date_end + 1:]
        return self._time_precision(time_part)

    def _date_precision(self, date_str):
        if len(date_str) == 4:
            return 'year'

        has_sep = date_str[4:5] == b'-'
        body = date_str[5:] if has_sep else date_str[4:]

        if body[:1] == b'W':
            # Www (3 characters) is week precision, anything with a day is
            # day precision.
            return 'week' if len(body) == 3 else 'day'

        if len(body) == 2:
            return 'month'

        return 'day'

    def _time_precision(self, time_str):
        cut = len(time_str)
        for pos, char in enumerate(time_str):
            if char in b'Zz+-':
                cut = pos
                break
                cut = index
                break

        body = time_str[:cut]
        if b'.' in body or b',' in body:
            return 'microsecond'

        digit_count = len(body.replace(b':', b''))
        if digit_count == 2:
            return 'hour'
        elif digit_count == 4:
            return 'minute'
        else:
            return 'second'


DEFAULT_ISOINTERVALPARSER = isointervalparser()
parse_interval = DEFAULT_ISOINTERVALPARSER.parse_interval
parse_isoduration = DEFAULT_ISOINTERVALPARSER.parse_isoduration
