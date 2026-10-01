# -*- coding: utf-8 -*-
"""
Work-time calendars for SLA-style computations.

This module provides :class:`WorkCalendar`, which describes when work
happens in a given time zone and measures *real elapsed* working time
between two moments, or shifts a moment by a given number of working
seconds.

Conventions
-----------

The semantics below are part of the public contract of this module:

* All results are measured in **real elapsed seconds** (UTC timeline),
  not in wall-clock seconds.  A one-hour wall-clock shift crossing a
  DST transition therefore contributes more or fewer than 3600 seconds.
* Work intervals are **half-open**: ``[start, end)``.  A moment exactly
  at a shift start is working; a moment exactly at a shift end is not.
* Overlapping intervals (within a day, or created by overnight shifts
  spilling into the next day) are **merged** before measuring, so
  overlapping work is never double counted.
* A span whose end time is not after its start time is an **overnight
  (cross-midnight)** shift ending on the following local day.  As a
  consequence ``(time(0, 0), time(0, 0))`` denotes a full 24-hour shift.
* Wall-clock endpoints are normalized in the calendar time zone before
  being mapped to the UTC timeline, independently of the ``tzinfo``
  implementation:

  - **DST gap (spring forward):** a nonexistent wall-clock endpoint is
    moved forward to the first real moment (equivalent to interpreting
    it with the pre-transition offset, see
    :func:`dateutil.tz.resolve_imaginary`).  A shift portion falling
    inside the gap therefore contributes zero real seconds.
  - **DST overlap (fall back):** an ambiguous wall-clock endpoint
    denotes its first occurrence (``fold=0``).  Real elapsed seconds
    are counted as they actually pass, so a repeated hour inside a
    shift is counted as real elapsed time.
* Per-date overrides **replace** the weekly template for that date
  entirely; mapping a date to ``None`` or an empty sequence makes it a
  full rest day (e.g. a holiday), while mapping it to spans declares
  ad-hoc work (e.g. temporary overtime).
* ``add_work(dt, 0)`` returns ``dt`` unchanged, and negative amounts
  move backwards in time.  ``work_between`` and ``add_work`` are
  mutually consistent: ``work_between(t, cal.add_work(t, s)) == s``
  for ``s >= 0`` whenever enough working time exists.
  Forward displacement from a non-working moment starts counting at
  the next shift start, so ``add_work(add_work(t, s), -s) == t`` holds
  exactly when ``t`` itself is a working moment.

No per-second iteration is used anywhere; time is computed by
intersecting whole intervals.
"""

from datetime import date, datetime, time, timedelta

from dateutil.tz import (UTC, datetime_ambiguous, datetime_exists, gettz,
                         resolve_imaginary)

__all__ = ["WorkCalendar"]

_ONE_DAY = timedelta(days=1)

# Safety bound for add_work(): scanning more than ~100 years of days
# without finding enough working time is treated as an error.
_MAX_SCAN_DAYS = 366 * 100


def _validate_spans(spans, where):
    """Normalize an iterable of ``(start_time, end_time)`` pairs."""
    normalized = []
    for span in spans:
        try:
            start_t, end_t = span
        except (TypeError, ValueError):
            raise ValueError(
                "%s: each span must be a (start, end) pair, got %r"
                % (where, span,)
            )
        for t in (start_t, end_t):
            if not isinstance(t, time):
                raise TypeError(
                    "%s: span endpoints must be datetime.time, got %r"
                    % (where, t,)
                )
            if t.tzinfo is not None:
                raise ValueError(
                    "%s: span endpoints must be naive wall-clock times, "
                    "got %r" % (where, t,)
                )
        normalized.append((start_t, end_t))
    return tuple(normalized)


class WorkCalendar(object):
    """
    A work-time calendar bound to a time zone.

    :param tz:
        The time zone the wall-clock schedules are expressed in.
        Either a ``tzinfo`` instance or an IANA key such as
        ``"America/New_York"`` (resolved with :func:`dateutil.tz.gettz`).
    :param weekly:
        The recurring weekly template: a mapping of weekday
        (Monday=0 .. Sunday=6, matching :meth:`datetime.date.weekday`)
        to an iterable of ``(start_time, end_time)`` naive
        :class:`datetime.time` pairs.  Missing weekdays are rest days.
    :param overrides:
        Per-date replacements: a mapping of :class:`datetime.date` to
        either ``None``/empty (a full rest day, e.g. a holiday) or an
        iterable of ``(start_time, end_time)`` pairs used instead of
        the weekly template for that date (e.g. temporary overtime).
    """

    def __init__(self, tz, weekly=None, overrides=None):
        if isinstance(tz, str):
            tz = gettz(tz)
        if tz is None:
            raise ValueError("tz must be a tzinfo instance or a valid "
                             "IANA time zone key")
        self.tz = tz

        self._weekly = {}
        for weekday, spans in (weekly or {}).items():
            if not isinstance(weekday, int) or not 0 <= weekday <= 6:
                raise ValueError(
                    "weekly keys must be weekdays 0 (Monday) .. 6 "
                    "(Sunday), got %r" % (weekday,)
                )
            self._weekly[weekday] = _validate_spans(
                spans, "weekly[%r]" % (weekday,))

        self._overrides = {}
        for day, spans in (overrides or {}).items():
            if not isinstance(day, date):
                raise TypeError(
                    "overrides keys must be datetime.date, got %r"
                    % (day,))
            if spans is None:
                self._overrides[day] = ()
            else:
                self._overrides[day] = _validate_spans(
                    spans, "overrides[%r]" % (day,))

    # ------------------------------------------------------------------
    # interval construction
    # ------------------------------------------------------------------
    def _spans_for_date(self, day):
        """Wall-clock spans in effect on local date ``day``."""
        if day in self._overrides:
            return self._overrides[day]
        return self._weekly.get(day.weekday(), ())

    def _resolve_wall(self, dt):
        """
        Normalize a wall-clock datetime to a real moment.

        Ambiguous times (DST overlap) resolve to their first
        occurrence; imaginary times (DST gap) fall forward to the
        first moment that actually exists.
        """
        if datetime_ambiguous(dt):
            dt = dt.replace(fold=0)
        elif not datetime_exists(dt):
            dt = resolve_imaginary(dt)
        return dt

    def _intervals_utc_for_date(self, day):
        """
        Merged, sorted ``(start_ts, end_ts)`` UTC timestamp intervals
        generated by the spans declared on local date ``day``.
        """
        intervals = []
        for start_t, end_t in self._spans_for_date(day):
            if end_t > start_t:
                end_day = day
            else:
                # Overnight shift (end <= start): ends the next day.
                # (00:00, 00:00) therefore means a full 24-hour shift.
                end_day = day + _ONE_DAY
            start_dt = self._resolve_wall(
                datetime.combine(day, start_t, tzinfo=self.tz))
            end_dt = self._resolve_wall(
                datetime.combine(end_day, end_t, tzinfo=self.tz))
            start_ts = start_dt.astimezone(UTC).timestamp()
            end_ts = end_dt.astimezone(UTC).timestamp()
            if end_ts > start_ts:
                intervals.append((start_ts, end_ts))

        intervals.sort()
        merged = []
        for start_ts, end_ts in intervals:
            if merged and start_ts <= merged[-1][1]:
                if end_ts > merged[-1][1]:
                    merged[-1] = (merged[-1][0], end_ts)
            else:
                merged.append((start_ts, end_ts))
        return merged

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _as_local(self, dt):
        """Interpret ``dt`` in the calendar time line."""
        if not isinstance(dt, datetime):
            raise TypeError("expected datetime, got %r" % (dt,))
        if dt.tzinfo is None:
            # Naive datetimes are read as local wall-clock times in the
            # calendar's time zone.
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    @staticmethod
    def _coerce_seconds(seconds):
        if isinstance(seconds, timedelta):
            return seconds.total_seconds()
        return float(seconds)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def is_working(self, dt):
        """Return ``True`` if ``dt`` falls inside a work interval."""
        local = self._as_local(dt)
        ts = local.astimezone(UTC).timestamp()
        day = local.date()
        for candidate in (day - _ONE_DAY, day):
            for start_ts, end_ts in self._intervals_utc_for_date(candidate):
                if start_ts <= ts < end_ts:
                    return True
        return False

    def work_between(self, start, end):
        """
        Real working seconds between ``start`` and ``end``.

        Returns ``0.0`` when ``end`` is not after ``start``.  Naive
        datetimes are read as local wall-clock times in the calendar's
        time zone.
        """
        start_local = self._as_local(start)
        end_local = self._as_local(end)
        t0 = start_local.astimezone(UTC).timestamp()
        t1 = end_local.astimezone(UTC).timestamp()
        if t1 <= t0:
            return 0.0

        # Merge intervals across the whole day range first: an
        # overnight shift spilling into the next day may overlap that
        # day's own spans, and overlaps must not be double counted.
        # Interval starts are generated in non-decreasing order, so a
        # single running merge is sufficient.
        merged = []
        day = start_local.date() - _ONE_DAY
        last_day = end_local.date()
        while day <= last_day:
            for start_ts, end_ts in self._intervals_utc_for_date(day):
                if merged and start_ts <= merged[-1][1]:
                    if end_ts > merged[-1][1]:
                        merged[-1] = (merged[-1][0], end_ts)
                else:
                    merged.append((start_ts, end_ts))
            day += _ONE_DAY

        total = 0.0
        for start_ts, end_ts in merged:
            lo = max(start_ts, t0)
            hi = min(end_ts, t1)
            if hi > lo:
                total += hi - lo
        return total

    def add_work(self, dt, seconds):
        """
        Shift ``dt`` by ``seconds`` of working time.

        Positive amounts move forward, negative amounts move backward,
        and ``0`` returns ``dt`` unchanged.  The result is an aware
        datetime expressed in the calendar's time zone.

        :raises ValueError:
            if not enough working time exists within about 100 years in
            the requested direction (e.g. the calendar declares no work
            at all).
        """
        seconds = self._coerce_seconds(seconds)
        if seconds == 0:
            return dt

        local = self._as_local(dt)
        remaining = abs(seconds)
        forward = seconds > 0
        ts = local.astimezone(UTC).timestamp()

        if forward:
            day = local.date() - _ONE_DAY
            step = _ONE_DAY
        else:
            day = local.date()
            step = -_ONE_DAY

        scanned = 0
        while scanned < _MAX_SCAN_DAYS:
            intervals = self._intervals_utc_for_date(day)
            if not forward:
                intervals = intervals[::-1]
            for start_ts, end_ts in intervals:
                if forward:
                    if ts >= end_ts:
                        continue
                    cursor = max(ts, start_ts)
                    available = end_ts - cursor
                    if remaining <= available:
                        result_ts = cursor + remaining
                        return datetime.fromtimestamp(
                            result_ts, UTC).astimezone(self.tz)
                    remaining -= available
                    ts = end_ts
                else:
                    if ts <= start_ts:
                        continue
                    cursor = min(ts, end_ts)
                    available = cursor - start_ts
                    if remaining <= available:
                        result_ts = cursor - remaining
                        return datetime.fromtimestamp(
                            result_ts, UTC).astimezone(self.tz)
                    remaining -= available
                    ts = start_ts
            day += step
            scanned += 1

        raise ValueError(
            "not enough working time in this calendar to shift by %r "
            "seconds" % (seconds,))
