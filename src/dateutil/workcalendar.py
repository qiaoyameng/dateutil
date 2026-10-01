# -*- coding: utf-8 -*-
"""
Work-time calendars for SLA-style computations.

This module provides :class:`WorkCalendar`, which describes *when* work
happens in a given time zone and answers two questions in real elapsed
seconds:

* how much work time accumulates between two instants
  (:meth:`WorkCalendar.work_seconds_between`), and
* which instant is reached after adding (or subtracting) a number of
  work seconds (:meth:`WorkCalendar.add_work_seconds`).

Conventions
-----------
The following conventions are fixed and part of the public contract:

* All arithmetic is performed on UTC instants and all durations are
  **real elapsed seconds**.  A shift that spans a DST transition is
  therefore longer or shorter in wall-clock terms, never in elapsed
  terms.
* The weekly schedule maps weekday numbers (``0`` = Monday ...
  ``6`` = Sunday, matching :meth:`datetime.date.weekday`) to lists of
  ``(start_time, end_time)`` pairs of naive :class:`datetime.time`
  objects, interpreted in the calendar's time zone.
* An interval with ``end_time < start_time`` crosses midnight and ends
  on the *next* local date.  ``end_time == start_time`` is rejected
  with :class:`ValueError` (its meaning would be ambiguous).
* Per-date overrides replace the weekly entry for that local date
  entirely: an empty list declares a full-day holiday, a custom list
  declares exceptional hours (e.g. weekend overtime).
* Overlapping or touching intervals -- whether declared on the same
  date or created by a night shift spilling into the next date -- are
  merged into their union and never counted twice.
* Intervals are half-open, ``[start, end)``: an instant exactly at the
  end of a work interval is not work time, but
  :meth:`~WorkCalendar.add_work_seconds` may land exactly on it when
  the requested seconds are exhausted precisely at the boundary.
* DST transitions (for zones with support for ``fold`` and imaginary
  detection, such as :class:`dateutil.tz.tzfile`):

  - *Ambiguous* wall times (repeated hour, "fall back") resolve to
    their **first** occurrence (``fold=0``).
  - *Imaginary* wall times (skipped hour, "spring forward") are
    shifted **forward** by the transition delta, via
    :func:`dateutil.tz.resolve_imaginary`.
  - An interval whose endpoints collapse onto each other after this
    resolution contributes zero seconds.

* Naive datetimes passed to the query methods are interpreted as wall
  times in the calendar's time zone (with the same ambiguous/imaginary
  rules); aware datetimes are used as-is.  ``add_work_seconds``
  returns a datetime matching the input's awareness: naive input
  yields a naive calendar-local result, aware input yields a result in
  the input's own time zone.
* ``work_seconds_between(end, start)`` with ``end < start`` returns
  the negated forward value, and ``add_work_seconds`` accepts negative
  seconds to move backwards.  Adding ``0`` seconds always returns the
  input unchanged, whether or not it falls inside work time.

No per-second (or per-minute) iteration is used anywhere: queries walk
whole intervals day by day.
"""

from __future__ import absolute_import, division, unicode_literals

import datetime
from datetime import timedelta

import six

from . import tz

__all__ = ["WorkCalendar"]

_ONE_DAY = timedelta(days=1)
_UTC = tz.UTC


def _validate_intervals(intervals, owner):
    checked = []
    for interval in intervals:
        try:
            start_t, end_t = interval
        except (TypeError, ValueError):
            raise ValueError(
                "%s entries must be (start_time, end_time) pairs, "
                "got %r" % (owner, interval))
        for t in (start_t, end_t):
            if not isinstance(t, datetime.time):
                raise TypeError(
                    "%s interval endpoints must be datetime.time, "
                    "got %r" % (owner, t))
            if t.tzinfo is not None:
                raise ValueError(
                    "%s interval endpoints must be naive times, "
                    "got %r" % (owner, t))
        if start_t == end_t:
            raise ValueError(
                "%s interval %r has start == end; use an explicit "
                "overnight interval (end < start) or drop it" %
                (owner, interval))
        checked.append((start_t, end_t))
    return tuple(checked)


class WorkCalendar(object):
    """
    A work-time calendar: time zone, weekly work intervals and
    per-date replacement intervals.

    :param timezone:
        A :class:`datetime.tzinfo` or an IANA zone name string
        (resolved with :func:`dateutil.tz.gettz`).  All schedule times
        are interpreted in this zone.

    :param weekly:
        Mapping of weekday numbers (``0`` = Monday ... ``6`` = Sunday)
        to iterables of ``(start_time, end_time)`` naive
        :class:`datetime.time` pairs.  Weekdays absent from the mapping
        are non-working days.  ``end_time < start_time`` means the
        interval crosses midnight into the next local date.

    :param overrides:
        Optional mapping of :class:`datetime.date` to an iterable of
        ``(start_time, end_time)`` pairs that *replaces* the weekly
        schedule for that local date.  Use an empty list for holidays
        and a custom list for exceptional hours such as overtime.

    .. doctest::

        >>> from datetime import date, datetime, time
        >>> from dateutil.workcalendar import WorkCalendar
        >>> cal = WorkCalendar(
        ...     "UTC",
        ...     weekly={i: [(time(9), time(17))] for i in range(5)},
        ...     overrides={date(2026, 1, 1): []},
        ... )
        >>> cal.work_seconds_between(datetime(2026, 1, 5, 9),
        ...                          datetime(2026, 1, 5, 17))
        28800.0
        >>> cal.add_work_seconds(datetime(2026, 1, 5, 16), 7200)
        datetime.datetime(2026, 1, 6, 10, 0)
    """

    def __init__(self, timezone, weekly, overrides=None):
        if isinstance(timezone, six.string_types):
            timezone = tz.gettz(timezone)
            if timezone is None:
                raise ValueError("Unknown time zone name")
        if not isinstance(timezone, datetime.tzinfo):
            raise TypeError(
                "timezone must be a tzinfo or an IANA name, got %r" %
                (timezone,))
        self._tz = timezone

        self._weekly = {}
        for weekday, intervals in (weekly or {}).items():
            if not isinstance(weekday, six.integer_types) or \
                    isinstance(weekday, bool) or not 0 <= weekday <= 6:
                raise ValueError(
                    "weekly keys must be weekday ints 0..6, got %r" %
                    (weekday,))
            checked = _validate_intervals(
                intervals, "weekly[%d]" % weekday)
            if checked:
                self._weekly[weekday] = checked

        self._overrides = {}
        for day, intervals in (overrides or {}).items():
            if isinstance(day, datetime.datetime) or \
                    not isinstance(day, datetime.date):
                raise TypeError(
                    "overrides keys must be datetime.date, got %r" %
                    (day,))
            self._overrides[day] = _validate_intervals(
                intervals, "overrides[%r]" % (day,))

    @property
    def timezone(self):
        """The calendar's :class:`datetime.tzinfo`."""
        return self._tz

    # -- interval generation -------------------------------------------

    def _local_intervals(self, day):
        """Declared (start, end) time pairs for a local date."""
        if day in self._overrides:
            return self._overrides[day]
        return self._weekly.get(day.weekday(), ())

    def _naive_to_utc(self, naive):
        """
        Convert a naive calendar-local datetime to a UTC datetime.

        Ambiguous wall times take their first occurrence (``fold=0``);
        imaginary wall times are shifted forward past the gap.
        """
        aware = naive.replace(tzinfo=self._tz)
        if not tz.datetime_exists(aware):
            aware = tz.resolve_imaginary(aware)
        return aware.astimezone(_UTC)

    def _utc_intervals_for_date(self, day):
        """
        Merged, sorted ``(utc_start, utc_end)`` work intervals declared
        on local date ``day`` (overnight intervals may spill into the
        next date).
        """
        intervals = []
        for start_t, end_t in self._local_intervals(day):
            naive_start = datetime.datetime.combine(day, start_t)
            if end_t > start_t:
                naive_end = datetime.datetime.combine(day, end_t)
            else:
                naive_end = datetime.datetime.combine(day + _ONE_DAY,
                                                      end_t)
            utc_start = self._naive_to_utc(naive_start)
            utc_end = self._naive_to_utc(naive_end)
            if utc_end > utc_start:
                intervals.append((utc_start, utc_end))
        intervals.sort()
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                if end > merged[-1][1]:
                    merged[-1] = (merged[-1][0], end)
            else:
                merged.append((start, end))
        return merged

    def _has_work_on_or_after(self, day):
        if self._weekly:
            return True
        return any(d >= day and intervals
                   for d, intervals in self._overrides.items())

    def _has_work_on_or_before(self, day):
        if self._weekly:
            return True
        return any(d <= day and intervals
                   for d, intervals in self._overrides.items())

    def _interval_stream(self, start_day):
        """
        Yield globally merged ``(utc_start, utc_end)`` intervals in
        chronological order, starting with local date ``start_day``.
        """
        pending = None
        day = start_day
        while True:
            if pending is None and not self._has_work_on_or_after(day):
                return
            intervals = self._utc_intervals_for_date(day)
            for start, end in intervals:
                if pending is None:
                    pending = [start, end]
                elif start <= pending[1]:
                    pending[1] = max(pending[1], end)
                else:
                    yield tuple(pending)
                    pending = [start, end]
            if not intervals and pending is not None:
                yield tuple(pending)
                pending = None
            day += _ONE_DAY

    def _interval_stream_backward(self, start_day):
        """
        Yield globally merged ``(utc_start, utc_end)`` intervals in
        reverse chronological order, starting with local date
        ``start_day``.
        """
        pending = None
        day = start_day
        while True:
            if pending is None and not self._has_work_on_or_before(day):
                return
            intervals = self._utc_intervals_for_date(day)
            for start, end in reversed(intervals):
                if pending is None:
                    pending = [start, end]
                elif end >= pending[0]:
                    pending[0] = min(pending[0], start)
                else:
                    yield tuple(pending)
                    pending = [start, end]
            if not intervals and pending is not None:
                yield tuple(pending)
                pending = None
            day -= _ONE_DAY

    # -- input normalization -------------------------------------------

    def _as_utc(self, dt):
        if not isinstance(dt, datetime.datetime):
            raise TypeError(
                "expected datetime.datetime, got %r" % (dt,))
        if dt.tzinfo is None:
            return self._naive_to_utc(dt.replace(tzinfo=None))
        return dt.astimezone(_UTC)

    # -- public API ----------------------------------------------------

    def work_seconds_between(self, start, end):
        """
        Real work seconds accumulated in the half-open interval
        ``[start, end)``.

        Naive datetimes are interpreted in the calendar's time zone.
        If ``end`` is earlier than ``start``, the negated value of the
        swapped call is returned.  Equal endpoints give ``0.0``.

        :return: elapsed work seconds as a float.
        """
        start_utc = self._as_utc(start)
        end_utc = self._as_utc(end)
        if end_utc < start_utc:
            return -self.work_seconds_between(end, start)
        if end_utc == start_utc:
            return 0.0

        first_day = start_utc.astimezone(self._tz).date() - _ONE_DAY
        last_day = end_utc.astimezone(self._tz).date()

        total = 0.0
        merged_start = None
        merged_end = None

        day = first_day
        while day <= last_day:
            for iv_start, iv_end in self._utc_intervals_for_date(day):
                if merged_start is not None and iv_start <= merged_end:
                    merged_end = max(merged_end, iv_end)
                else:
                    if merged_start is not None:
                        lo = max(merged_start, start_utc)
                        hi = min(merged_end, end_utc)
                        if hi > lo:
                            total += (hi - lo).total_seconds()
                    merged_start, merged_end = iv_start, iv_end
            day += _ONE_DAY
        if merged_start is not None:
            lo = max(merged_start, start_utc)
            hi = min(merged_end, end_utc)
            if hi > lo:
                total += (hi - lo).total_seconds()
        return total

    def add_work_seconds(self, dt, seconds):
        """
        Instant reached after accumulating ``seconds`` of work time
        from ``dt`` (negative values move backwards).

        If ``dt`` falls outside work time, accumulation starts at the
        next (or, for negative values, previous) work interval.
        Landing exactly on an interval boundary returns that boundary
        instant.  ``seconds == 0`` returns ``dt`` unchanged.

        Naive input is interpreted in the calendar's time zone and
        produces a naive result; aware input produces a result in the
        input's own time zone.

        :raises ValueError: if the calendar contains no work time in
            the requested direction.
        """
        if not isinstance(seconds, six.integer_types + (float,)):
            raise TypeError(
                "seconds must be a number, got %r" % (seconds,))
        aware_input = dt.tzinfo is not None
        out_tz = dt.tzinfo if aware_input else None
        cur = self._as_utc(dt)

        if seconds == 0:
            return dt
        elif seconds > 0:
            result = self._shift_forward(cur, float(seconds))
        else:
            result = self._shift_backward(cur, float(-seconds))

        if aware_input:
            return result.astimezone(out_tz)
        return result.astimezone(self._tz).replace(tzinfo=None)

    def _shift_forward(self, cur, remaining):
        day = cur.astimezone(self._tz).date() - _ONE_DAY
        for start, end in self._interval_stream(day):
            if end <= cur:
                continue
            if cur < start:
                cur = start
            available = (end - cur).total_seconds()
            if remaining < available:
                return cur + timedelta(seconds=remaining)
            remaining -= available
            cur = end
            if remaining == 0:
                return cur
        raise ValueError(
            "calendar has no work time on or after %r" % (cur,))

    def _shift_backward(self, cur, remaining):
        day = cur.astimezone(self._tz).date() + _ONE_DAY
        for start, end in self._interval_stream_backward(day):
            if start >= cur:
                continue
            if cur > end:
                cur = end
            available = (cur - start).total_seconds()
            if remaining < available:
                return cur - timedelta(seconds=remaining)
            remaining -= available
            cur = start
            if remaining == 0:
                return cur
        raise ValueError(
            "calendar has no work time on or before %r" % (cur,))
