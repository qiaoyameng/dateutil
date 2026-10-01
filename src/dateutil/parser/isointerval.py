# -*- coding: utf-8 -*-
"""
This module offers a parser for ISO-8601 time interval strings.

ISO-8601 intervals are expressed as two components separated by a solidus
(``/``), in one of the following forms:

- ``<start>/<end>``
- ``<start>/<duration>``
- ``<duration>/<end>``

Either end may also be left explicitly open by leaving the component empty
or using the ``..`` token (e.g. ``2017-01-01/`` or ``../2017-02-01``), in
which case the interval is unbounded on that side.

Durations use the ISO-8601 ``PnYnMnDTnHnMnS`` format. Durations involving
years or months are applied with calendar semantics (via
:class:`dateutil.relativedelta.relativedelta`) rather than being converted
to a fixed number of seconds, so ``2017-01-31/P1M`` ends on
``2017-02-28`` (or ``2016-02-29`` in a leap year).
"""
import re

from dateutil.relativedelta import relativedelta

from .isoparser import isoparser, _takes_ascii

__all__ = ["ISOInterval", "isointervalparse", "isointervalparser"]


#: Precision levels, ordered from coarsest to finest.
_PRECISIONS = ('year', 'month', 'day', 'hour', 'minute', 'second',
               'microsecond')


class ISOInterval(object):
    """
    The result of parsing an ISO-8601 interval string.

    :ivar start:
        The start of the interval as a :class:`datetime.datetime`, or
        ``None`` if the start of the interval is open.

    :ivar end:
        The end of the interval as a :class:`datetime.datetime`, or
        ``None`` if the end of the interval is open.

    :ivar start_open:
        Whether the start of the interval was explicitly left open.

    :ivar end_open:
        Whether the end of the interval was explicitly left open.

    :ivar precision:
        The precision of the datetime components of the input string, one
        of ``'year'``, ``'month'``, ``'day'``, ``'hour'``, ``'minute'``,
        ``'second'`` or ``'microsecond'``. When both endpoints were given
        as datetimes, this is the *coarser* of the two precisions.
    """
    __slots__ = ('start', 'end', 'start_open', 'end_open', 'precision')

    def __init__(self, start, end, start_open, end_open, precision):
        self.start = start
        self.end = end
        self.start_open = start_open
        self.end_open = end_open
        self.precision = precision

    def __eq__(self, other):
        if not isinstance(other, ISOInterval):
            return NotImplemented

        return (self.start == other.start and
                self.end == other.end and
                self.start_open == other.start_open and
                self.end_open == other.end_open and
                self.precision == other.precision)

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return eq
        return not eq

    def __repr__(self):
        return ('{cls}(start={start!r}, end={end!r}, '
                'start_open={start_open!r}, end_open={end_open!r}, '
                'precision={precision!r})').format(
                    cls=type(self).__name__,
                    start=self.start, end=self.end,
                    start_open=self.start_open, end_open=self.end_open,
                    precision=self.precision)


class isointervalparser(object):
    """
    Parser for ISO-8601 interval strings.

    :param sep:
        A single character that separates date and time portions of the
        datetime endpoints. If ``None``, the parser will accept any single
        character. For strict ISO-8601 adherence, pass ``'T'``.
    """
    def __init__(self, sep=None):
        self._isoparser = isoparser(sep=sep)

    @_takes_ascii
    def parse_isointerval(self, interval_str):
        """
        Parse an ISO-8601 interval string into an :class:`ISOInterval`.

        Supported forms are ``<start>/<end>``, ``<start>/<duration>`` and
        ``<duration>/<end>``, where datetimes are any string accepted by
        :func:`dateutil.parser.isoparse` and durations use the ISO-8601
        ``PnYnMnDTnHnMnS`` format. Either end may be left explicitly open
        with an empty component or the ``..`` token.

        :param interval_str:
            A string or stream containing only an ISO-8601 interval string

        :return:
            Returns an :class:`ISOInterval` with the resolved endpoints,
            the openness of each boundary and the precision of the input.

        :raises ValueError:
            Raised when the string is not a valid interval, when the end
            precedes the start, when the two endpoints have inconsistent
            time zone information, or when the duration is negative.

        Examples:

        .. code-block:: python3

            >>> from dateutil.parser import isointervalparse
            >>> isointervalparse('2017-01-31/P1M')  # calendar semantics
            ISOInterval(start=datetime.datetime(2017, 1, 31, 0, 0), ...
            >>> isointervalparse('2017-01-01T00:00:00.5/2017-01-01T00:00:01.25')
            ISOInterval(..., precision='microsecond')
        """
        parts = interval_str.split(b'/')
        if len(parts) != 2:
            raise ValueError(
                'Invalid ISO-8601 interval: {!r}'.format(
                    interval_str.decode('ascii')))

        start_kind = self._classify_component(parts[0])
        end_kind = self._classify_component(parts[1])

        if start_kind == 'open' and end_kind == 'open':
            raise ValueError(
                'At least one end of an interval must be specified')

        if ((start_kind == 'duration' and end_kind != 'datetime') or
                (end_kind == 'duration' and start_kind != 'datetime')):
            raise ValueError(
                'A duration must be anchored to a datetime at one end of '
                'the interval')

        start = end = None
        start_open = end_open = False
        precisions = []

        if start_kind == 'datetime':
            start = self._isoparser.isoparse(parts[0])
            precisions.append(self._datetime_precision(parts[0]))
        elif start_kind == 'open':
            start_open = True

        if end_kind == 'datetime':
            end = self._isoparser.isoparse(parts[1])
            precisions.append(self._datetime_precision(parts[1]))
        elif end_kind == 'open':
            end_open = True

        if start_kind == 'duration':
            start = end - self._parse_duration(parts[0])
        elif end_kind == 'duration':
            end = start + self._parse_duration(parts[1])

        if start is not None and end is not None:
            if (start.tzinfo is None) != (end.tzinfo is None):
                raise ValueError(
                    'Interval endpoints have inconsistent time zone '
                    'information: {!r} and {!r}'.format(
                        parts[0].decode('ascii'), parts[1].decode('ascii')))

            if end < start:
                raise ValueError(
                    'Interval end {!r} is before interval start '
                    '{!r}'.format(end, start))

        precision = min(precisions, key=_PRECISIONS.index)

        return ISOInterval(start=start, end=end,
                           start_open=start_open, end_open=end_open,
                           precision=precision)

    # Class-level constants
    _OPEN_TOKENS = (b'', b'..')

    _DURATION_REGEX = re.compile(
        b'P'
        b'(?:(?P<years>[0-9]+(?:[.,][0-9]+)?)Y)?'
        b'(?:(?P<months>[0-9]+(?:[.,][0-9]+)?)M)?'
        b'(?:(?P<weeks>[0-9]+(?:[.,][0-9]+)?)W)?'
        b'(?:(?P<days>[0-9]+(?:[.,][0-9]+)?)D)?'
        b'(?:T'
        b'(?:(?P<hours>[0-9]+(?:[.,][0-9]+)?)H)?'
        b'(?:(?P<minutes>[0-9]+(?:[.,][0-9]+)?)M)?'
        b'(?:(?P<seconds>[0-9]+(?:[.,][0-9]+)?)S)?'
        b')?$')

    _TIME_PRECISION_REGEX = re.compile(
        b'^(?P<hour>[0-9]{2})'
        b'(?::?(?P<minute>[0-9]{2}))?'
        b'(?::?(?P<second>[0-9]{2}))?'
        b'(?P<fraction>[.,][0-9]+)?')

    def _classify_component(self, component):
        if component in self._OPEN_TOKENS:
            return 'open'

        if component.startswith(b'P') or component.startswith(b'-P'):
            return 'duration'

        return 'datetime'

    def _parse_duration(self, dur_str):
        """
        Parse an ISO-8601 duration into a :class:`relativedelta`.

        Years and months retain their calendar meaning and are *not*
        converted into a fixed number of seconds.
        """
        if dur_str.startswith(b'-'):
            raise ValueError(
                'Interval durations may not be negative: {!r}'.format(
                    dur_str.decode('ascii')))

        match = self._DURATION_REGEX.match(dur_str)
        if match is None:
            raise ValueError(
                'Invalid ISO-8601 duration: {!r}'.format(
                    dur_str.decode('ascii')))

        groups = match.groupdict()
        if all(value is None for value in groups.values()):
            raise ValueError(
                'Duration specifies no components: {!r}'.format(
                    dur_str.decode('ascii')))

        values = {}
        for key, value in groups.items():
            if value is None:
                continue

            number = float(value.replace(b',', b'.'))
            if key in ('years', 'months'):
                if not number.is_integer():
                    raise ValueError(
                        'Fractional {} are ambiguous and not supported in '
                        'interval durations: {!r}'.format(
                            key, dur_str.decode('ascii')))
                number = int(number)
            values[key] = number

        weeks = values.pop('weeks', 0)
        values['days'] = values.get('days', 0) + weeks * 7

        return relativedelta(**values)

    def _datetime_precision(self, dt_str):
        """
        Determine the precision of an ISO-8601 datetime string.
        """
        components, pos = self._isoparser._parse_isodate(dt_str)

        if pos == 4:
            precision = 'year'
        elif pos == 7 and dt_str[4:5] == b'-':
            # YYYY-MM (all other 7-character formats are day-precision)
            precision = 'month'
        else:
            precision = 'day'

        if len(dt_str) > pos:
            timestr = dt_str[pos + 1:]
            match = self._TIME_PRECISION_REGEX.match(timestr)
            if match.group('fraction') is not None:
                precision = 'microsecond'
            elif match.group('second') is not None:
                precision = 'second'
            elif match.group('minute') is not None:
                precision = 'minute'
            else:
                precision = 'hour'

        return precision


DEFAULT_ISOINTERVALPARSER = isointervalparser()
isointervalparse = DEFAULT_ISOINTERVALPARSER.parse_isointerval
