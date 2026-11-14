"""
This module provides an explicit parser for ISO 8601 *time intervals*
(``start/end``, ``start/duration`` and ``duration/end``).

It is deliberately separate from :func:`dateutil.parser.isoparse`, which
continues to accept only single dates and datetimes; interval strings
(containing a ``/``) are not silently accepted there.

Supported scope (first version)
-------------------------------

Interval forms:

- ``start/end``, ``start/duration`` and ``duration/end``
- an explicitly open endpoint written as ``..`` (ISO 8601-2), e.g.
  ``../2024-03-01``, ``2024-03-01/..``, ``../P1M`` or ``P1M/..``

Endpoints:

- calendar dates ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD`` (extended) and
  ``YYYYMMDD`` (basic), with an optional time ``Thh``, ``Thh:mm``,
  ``Thh:mm:ss`` (or the basic ``Thhmm`` / ``Thhmmss``), optional
  fractional seconds (``.`` or ``,``, 1-6 digits) and an optional UTC
  offset ``Z`` or ``+-hh:mm`` / ``+-hhmm``
- reduced-precision endpoints default their missing components to the
  earliest value (January, day 1, midnight), matching ``isoparse``; the
  original precision is recorded on the interval so no information is
  lost

Durations:

- ``PnW`` or ``PnYnMnDTnHnMnS`` with integer components, plus a fraction
  on the seconds component only; years and months are kept as calendar
  components (``relativedelta``), so ``P1M`` is one calendar month and
  is never converted to a fixed number of days

Rules
-----

- Negative durations and intervals whose end precedes their start are
  rejected.
- Mixing an aware endpoint with a naive one is rejected; two aware
  endpoints with different UTC offsets are fine, and their duration is
  computed between the instants they denote.
- Inferring a start from ``duration/end`` uses calendar arithmetic; if
  the result lands on a day of the month that had to be clamped (so
  that more than one start date would map to the same end), the
  interval is rejected as ambiguous rather than silently picking a day.
- Inputs that cannot be expressed exactly are rejected: fractional
  years/months/weeks/days/hours/minutes, more than 6 fractional second
  digits, week dates, ordinal dates and signed durations.

Errors raise :class:`IntervalParseError`, whose ``component`` attribute
identifies the invalid part of the interval.
"""

import re
from datetime import timezone

from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta

__all__ = ["isointerval", "parse_isointerval", "IntervalParseError"]


class IntervalParseError(ValueError):
    """
    Raised when an ISO 8601 interval string cannot be parsed.

    :ivar component: which part of the interval is invalid: ``'start'``,
        ``'end'``, ``'duration'`` or ``'interval'`` (for problems with
        the interval as a whole, such as a missing separator or an end
        that precedes the start).
    :ivar value: the offending (sub)string.
    """

    def __init__(self, message, component="interval", value=None):
        super(IntervalParseError, self).__init__(message)
        self.component = component
        self.value = value


_PRECISIONS = ("year", "month", "day", "hour", "minute", "second", "fraction")

_ENDPOINT_RE = re.compile(
    r"""
    ^(?P<year>\d{4})
    (?:-?(?P<month>\d{2})(?:-?(?P<day>\d{2}))?)?
    (?:T(?P<hour>\d{2})
        (?::?(?P<minute>\d{2})
            (?::?(?P<second>\d{2})
                (?:[.,](?P<fraction>\d+))?
            )?
        )?
        (?P<utc_offset>Z|[+-]\d{2}(?::?\d{2})?)?
    )?$
    """,
    re.VERBOSE,
)

_DURATION_RE = re.compile(
    r"""
    ^P(?:
        (?P<weeks>\d+(?:[.,]\d+)?)W
      | (?:(?P<years>\d+(?:[.,]\d+)?)Y)?
        (?:(?P<months>\d+(?:[.,]\d+)?)M)?
        (?:(?P<days>\d+(?:[.,]\d+)?)D)?
        (?:T(?:(?P<hours>\d+(?:[.,]\d+)?)H)?
           (?:(?P<minutes>\d+(?:[.,]\d+)?)M)?
           (?:(?P<seconds>\d+(?:[.,]\d+)?)S)?
        )?
    )$
    """,
    re.VERBOSE,
)

# Duration components in the order they appear in an ISO 8601 duration.
_DURATION_UNITS = (
    "years",
    "months",
    "weeks",
    "days",
    "hours",
    "minutes",
    "seconds",
)


def _finer(precision1, precision2):
    if _PRECISIONS.index(precision1) >= _PRECISIONS.index(precision2):
        return precision1
    return precision2


def _parse_endpoint(text, component):
    match = _ENDPOINT_RE.match(text)
    if match is None:
        raise IntervalParseError(
            "Invalid or unsupported {0} endpoint: {1!r}".format(component, text),
            component=component,
            value=text,
        )

    fraction = match.group("fraction")
    if fraction is not None and len(fraction) > 6:
        raise IntervalParseError(
            "Sub-second precision beyond 6 digits cannot be represented "
            "exactly: {0!r}".format(text),
            component=component,
            value=text,
        )

    try:
        value = isoparse(text)
    except (ValueError, OverflowError) as exc:
        raise IntervalParseError(
            "Invalid {0} endpoint {1!r}: {2}".format(component, text, exc),
            component=component,
            value=text,
        )

    precision = "year"
    for group_name, group_precision in (
        ("fraction", "fraction"),
        ("second", "second"),
        ("minute", "minute"),
        ("hour", "hour"),
        ("day", "day"),
        ("month", "month"),
    ):
        if match.group(group_name) is not None:
            precision = group_precision
            break

    fraction_digits = len(fraction) if fraction is not None else 0
    return value, precision, fraction_digits


def _parse_duration(text):
    if text.startswith(("-", "+")):
        raise IntervalParseError(
            "Signed durations are not supported: {0!r}".format(text),
            component="duration",
            value=text,
        )

    match = _DURATION_RE.match(text)
    if match is None or not any(match.groupdict().values()):
        raise IntervalParseError(
            "Invalid duration: {0!r}".format(text),
            component="duration",
            value=text,
        )

    values = {}
    for name in _DURATION_UNITS:
        raw = match.group(name)
        if raw is None:
            continue
        integer, separator, fraction = raw.partition(".")
        if not separator:
            integer, separator, fraction = raw.partition(",")
        if separator:
            if name != "seconds":
                raise IntervalParseError(
                    "Fractional {0} cannot be represented exactly: "
                    "{1!r}".format(name, text),
                    component="duration",
                    value=text,
                )
            if len(fraction) > 6:
                raise IntervalParseError(
                    "Sub-second precision beyond 6 digits cannot be "
                    "represented exactly: {0!r}".format(text),
                    component="duration",
                    value=text,
                )
            values["microseconds"] = int(fraction.ljust(6, "0"))
        values[name] = int(integer)

    duration = relativedelta(
        years=values.get("years", 0),
        months=values.get("months", 0),
        days=values.get("days", 0) + 7 * values.get("weeks", 0),
        hours=values.get("hours", 0),
        minutes=values.get("minutes", 0),
        seconds=values.get("seconds", 0),
        microseconds=values.get("microseconds", 0),
    )

    # The precision is derived from the normalized duration (relativedelta
    # carries smaller units into larger ones), so that it always matches
    # the canonical encoding produced by _format_duration.
    precision = "day"
    fraction_digits = 0
    for attr, unit_precision in (
        ("microseconds", "fraction"),
        ("seconds", "second"),
        ("minutes", "minute"),
        ("hours", "hour"),
        ("days", "day"),
        ("months", "month"),
        ("years", "year"),
    ):
        if getattr(duration, attr):
            precision = unit_precision
            if attr == "microseconds":
                fraction_digits = len(
                    "{0:06d}".format(duration.microseconds).rstrip("0")
                )
            break

    return duration, precision, fraction_digits


def _format_endpoint(value, precision, fraction_digits):
    if value is None:
        return ".."

    text = "{0:04d}".format(value.year)
    if precision == "year":
        return text
    text += "-{0:02d}".format(value.month)
    if precision == "month":
        return text
    text += "-{0:02d}".format(value.day)
    if precision == "day":
        return text

    text += "T{0:02d}".format(value.hour)
    if precision == "hour":
        return _append_utc_offset(text, value)
    text += ":{0:02d}".format(value.minute)
    if precision == "minute":
        return _append_utc_offset(text, value)
    text += ":{0:02d}".format(value.second)
    if precision == "fraction":
        text += "." + "{0:06d}".format(value.microsecond)[:fraction_digits]
    return _append_utc_offset(text, value)


def _append_utc_offset(text, value):
    if value.tzinfo is None:
        return text
    offset = value.utcoffset()
    total_seconds = offset.days * 86400 + offset.seconds
    if total_seconds == 0:
        return text + "Z"
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    return "{0}{1}{2:02d}:{3:02d}".format(
        text, sign, total_seconds // 3600, (total_seconds % 3600) // 60
    )


def _format_duration(duration):
    date_parts = []
    if duration.years:
        date_parts.append("{0}Y".format(duration.years))
    if duration.months:
        date_parts.append("{0}M".format(duration.months))
    if duration.days:
        date_parts.append("{0}D".format(duration.days))

    time_parts = []
    if duration.hours:
        time_parts.append("{0}H".format(duration.hours))
    if duration.minutes:
        time_parts.append("{0}M".format(duration.minutes))
    if duration.seconds or duration.microseconds:
        seconds = "{0}".format(duration.seconds)
        if duration.microseconds:
            seconds += "." + "{0:06d}".format(duration.microseconds).rstrip("0")
        time_parts.append(seconds + "S")

    if not date_parts and not time_parts:
        return "P0D"
    text = "P" + "".join(date_parts)
    if time_parts:
        text += "T" + "".join(time_parts)
    return text


def _classify(part):
    if part == "..":
        return "open"
    if part.startswith(("P", "-P", "+P")):
        return "duration"
    return "endpoint"


def _instant_key(value):
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class isointerval(object):
    """
    An ISO 8601 time interval.

    Instances are created with :func:`parse_isointerval`.

    :ivar start: the start of the interval as a ``datetime``, or ``None``
        for an open start.
    :ivar end: the end of the interval as a ``datetime``, or ``None`` for
        an open end.
    :ivar duration: the length of the interval as a
        :class:`dateutil.relativedelta.relativedelta` (keeping any year
        and month components), or ``None`` if it cannot be determined
        (an open interval without an explicit duration).
    :ivar start_precision: precision of the ``start`` endpoint in the
        input: one of ``'year'``, ``'month'``, ``'day'``, ``'hour'``,
        ``'minute'``, ``'second'`` or ``'fraction'``.
    :ivar end_precision: precision of the ``end`` endpoint in the input.
    :ivar start_fraction_digits: number of fractional second digits in
        the ``start`` endpoint of the input (0 unless the precision is
        ``'fraction'``).
    :ivar end_fraction_digits: number of fractional second digits in the
        ``end`` endpoint of the input.
    """

    def __init__(
        self,
        start=None,
        end=None,
        duration=None,
        start_precision=None,
        end_precision=None,
        start_fraction_digits=0,
        end_fraction_digits=0,
        form="start_end",
    ):
        self.start = start
        self.end = end
        self.duration = duration
        self.start_precision = start_precision
        self.end_precision = end_precision
        self.start_fraction_digits = start_fraction_digits
        self.end_fraction_digits = end_fraction_digits
        self._form = form

    def _key(self):
        def endpoint_key(value):
            if value is None:
                return None
            return (value.tzinfo is not None, _instant_key(value))

        if self.duration is None:
            duration_key = None
        else:
            duration_key = tuple(
                getattr(self.duration, attr)
                for attr in (
                    "years",
                    "months",
                    "days",
                    "hours",
                    "minutes",
                    "seconds",
                    "microseconds",
                )
            )

        return (
            endpoint_key(self.start),
            endpoint_key(self.end),
            duration_key,
            self.start_precision,
            self.end_precision,
            self.start_fraction_digits,
            self.end_fraction_digits,
        )

    def __eq__(self, other):
        if not isinstance(other, isointerval):
            return NotImplemented
        return self._key() == other._key()

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def to_iso(self):
        """
        Encode the interval as an ISO 8601 string, in the same form
        (``start/end``, ``start/duration`` or ``duration/end``) as the
        input it was parsed from. Reparsing the result yields an equal
        interval.
        """
        start_text = _format_endpoint(
            self.start, self.start_precision, self.start_fraction_digits
        )
        end_text = _format_endpoint(
            self.end, self.end_precision, self.end_fraction_digits
        )

        if self._form == "start_end":
            return start_text + "/" + end_text

        duration_text = _format_duration(self.duration)
        if self._form == "start_duration":
            return start_text + "/" + duration_text
        if self._form == "duration_end":
            return duration_text + "/" + end_text
        if self._form == "open_duration":
            return "../" + duration_text
        return duration_text + "/.."

    def __str__(self):
        return self.to_iso()

    def __repr__(self):
        return "isointerval({0!r})".format(self.to_iso())


def parse_isointerval(value):
    """
    Parse an ISO 8601 interval string into an :class:`isointerval`.

    See the module documentation for the supported forms and the rules
    for reduced precision, open endpoints, negative durations, mixed
    aware/naive endpoints and ambiguous month-end inference.

    :raises IntervalParseError: if the string is not a supported,
        exactly representable interval.
    """
    if not isinstance(value, str):
        raise TypeError(
            "parse_isointerval() requires a str, not {0}".format(
                type(value).__name__
            )
        )

    parts = value.split("/")
    if len(parts) != 2:
        raise IntervalParseError(
            "An ISO 8601 interval must contain exactly one '/': "
            "{0!r}".format(value),
            component="interval",
            value=value,
        )

    kinds = [_classify(part) for part in parts]
    if kinds == ["open", "open"]:
        raise IntervalParseError(
            "An interval needs at least one endpoint: {0!r}".format(value),
            component="interval",
            value=value,
        )
    if kinds == ["duration", "duration"]:
        raise IntervalParseError(
            "An interval cannot contain two durations: {0!r}".format(value),
            component="interval",
            value=value,
        )

    start = end = duration = None
    start_precision = end_precision = None
    start_fraction_digits = end_fraction_digits = 0
    duration_precision = "day"
    duration_fraction_digits = 0

    first, second = parts
    if kinds[0] == "endpoint":
        start, start_precision, start_fraction_digits = _parse_endpoint(
            first, "start"
        )
    if kinds[1] == "endpoint":
        end, end_precision, end_fraction_digits = _parse_endpoint(second, "end")
    if "duration" in kinds:
        duration_text = first if kinds[0] == "duration" else second
        duration, duration_precision, duration_fraction_digits = _parse_duration(
            duration_text
        )

    if kinds == ["endpoint", "endpoint"]:
        form = "start_end"
    elif kinds == ["endpoint", "duration"]:
        form = "start_duration"
    elif kinds == ["duration", "endpoint"]:
        form = "duration_end"
    elif kinds == ["open", "duration"]:
        form = "open_duration"
    elif kinds == ["duration", "open"]:
        form = "duration_open"
    else:
        form = "start_end"

    if start is not None and end is not None:
        if (start.tzinfo is None) != (end.tzinfo is None):
            raise IntervalParseError(
                "Cannot mix an aware endpoint with a naive one: "
                "{0!r}".format(value),
                component="interval",
                value=value,
            )
        if _instant_key(end) < _instant_key(start):
            raise IntervalParseError(
                "The end of the interval precedes its start: "
                "{0!r}".format(value),
                component="interval",
                value=value,
            )
        if start.tzinfo is not None:
            duration = relativedelta(
                end.astimezone(timezone.utc), start.astimezone(timezone.utc)
            )
        else:
            duration = relativedelta(end, start)
    elif form == "start_duration":
        end = start + duration
        end_precision = _finer(start_precision, duration_precision)
        if end_precision == "fraction":
            end_fraction_digits = max(
                start_fraction_digits, duration_fraction_digits
            )
    elif form == "duration_end":
        start = end - duration
        if start + duration != end:
            raise IntervalParseError(
                "Cannot infer an unambiguous start for {0!r}: subtracting "
                "the duration from {1} lands on a clamped day of the "
                "month".format(value, end.isoformat()),
                component="interval",
                value=value,
            )
        start_precision = _finer(end_precision, duration_precision)
        if start_precision == "fraction":
            start_fraction_digits = max(
                end_fraction_digits, duration_fraction_digits
            )

    return isointerval(
        start=start,
        end=end,
        duration=duration,
        start_precision=start_precision,
        end_precision=end_precision,
        start_fraction_digits=start_fraction_digits,
        end_fraction_digits=end_fraction_digits,
        form=form,
    )
