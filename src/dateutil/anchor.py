"""
Anchored calendar sequences.

Unlike repeatedly adding :class:`dateutil.relativedelta.relativedelta`,
which drifts when a short month truncates the day of month, an anchored
calendar sequence computes every occurrence from the original anchor date.
"""

import calendar
import datetime

from .tz import datetime_ambiguous, datetime_exists, enfold, resolve_imaginary

__all__ = [
    "anchored_calendar",
    "CLAMP",
    "SKIP",
    "GAP_RAISE",
    "GAP_SKIP",
    "GAP_FIRST",
    "GAP_LAST",
    "FOLD_RAISE",
    "FOLD_FIRST",
    "FOLD_LAST",
]

CLAMP = "clamp"
SKIP = "skip"

GAP_RAISE = "raise"
GAP_SKIP = "skip"
GAP_FIRST = "first"
GAP_LAST = "last"

FOLD_RAISE = "raise"
FOLD_FIRST = "first"
FOLD_LAST = "last"

_INVALID_DATE_POLICIES = (CLAMP, SKIP)
_GAP_POLICIES = (GAP_RAISE, GAP_SKIP, GAP_FIRST, GAP_LAST)
_FOLD_POLICIES = (FOLD_RAISE, FOLD_FIRST, FOLD_LAST)


def _split_month_index(index):
    """Map a zero-based month index onto a (year, one-based month) pair."""
    index = int(index)
    year, month = divmod(index, 12)
    return year, month + 1


class anchored_calendar:
    """
    A calendar sequence where every occurrence is computed from an anchor.

    Each occurrence at period ``n`` is built from ``anchor`` by stepping
    ``n * interval`` calendar months without ever feeding a truncated result
    back into the next step, so an anchor of January 31 returns January 31
    again after a February occurrence rather than being pinned to the 28th::

        >>> from datetime import date
        >>> from dateutil.anchor import anchored_calendar
        >>> seq = anchored_calendar(date(2024, 1, 31))
        >>> seq.get(0)
        datetime.date(2024, 1, 31)
        >>> seq.get(1)
        datetime.date(2024, 2, 29)
        >>> seq.get(2)
        datetime.date(2024, 3, 31)

    :param anchor:
        The zero-th occurrence, as a :class:`datetime.date` or
        :class:`datetime.datetime`. Time components, including the time zone
        of an aware datetime, are preserved on every occurrence.

    :param interval:
        Number of calendar months between occurrences. Must be non-zero;
        negative values walk backwards.

    :param invalid_date:
        How to handle a period whose anchor day does not exist in its month:

        - ``CLAMP`` (the default): use the last valid day of the month.
        - ``SKIP``: omit the period entirely.

    :param month_end:
        Whether the anchor denotes the end of the month. With ``True`` each
        occurrence is the last day of its month regardless of the anchor
        day. With ``False`` the anchor's day of month is used and only
        clamped or skipped when it does not exist. The default of ``None``
        treats an anchor that is already the last day of its month as a
        month-end anchor and any other anchor as a fixed day of month.

    :param gap_policy:
        Policy for a wall time that does not exist in the anchor's time zone
        (a spring-forward gap): raise, skip the period, or resolve to the
        first or last existing wall time around the gap.

    :param fold_policy:
        Policy for an ambiguous wall time (a fall-back fold): raise, take
        the first occurrence (``fold=0``), or take the second
        (``fold=1``).
    """

    def __init__(self, anchor, interval=1, *, month_end=None,
                 invalid_date=CLAMP, gap_policy=GAP_RAISE,
                 fold_policy=FOLD_RAISE):
        if not isinstance(anchor, datetime.date):
            raise TypeError("anchor must be a datetime.date or "
                            "datetime.datetime instance")

        interval = int(interval)
        if interval == 0:
            raise ValueError("interval must be non-zero")

        if invalid_date not in _INVALID_DATE_POLICIES:
            raise ValueError("invalid_date must be one of %r" %
                             (_INVALID_DATE_POLICIES,))
        if gap_policy not in _GAP_POLICIES:
            raise ValueError("gap_policy must be one of %r" % (_GAP_POLICIES,))
        if fold_policy not in _FOLD_POLICIES:
            raise ValueError("fold_policy must be one of %r" %
                             (_FOLD_POLICIES,))

        if month_end is None:
            # A skip policy only makes sense for a fixed day of month: a
            # month-end anchor exists in every month and is never skipped.
            month_end = invalid_date != SKIP and (
                anchor.day ==
                calendar.monthrange(anchor.year, anchor.month)[1])

        self.anchor = anchor
        self.interval = interval
        self.invalid_date = invalid_date
        self.month_end = bool(month_end)
        self.gap_policy = gap_policy
        self.fold_policy = fold_policy

    def __repr__(self):
        return ("%s(%r, interval=%r, invalid_date=%r, month_end=%r, "
                "gap_policy=%r, fold_policy=%r)" %
                (type(self).__name__, self.anchor, self.interval,
                 self.invalid_date, self.month_end, self.gap_policy,
                 self.fold_policy))

    def __eq__(self, other):
        if not isinstance(other, anchored_calendar):
            return NotImplemented
        return (self.anchor == other.anchor and
                self.interval == other.interval and
                self.invalid_date == other.invalid_date and
                self.month_end == other.month_end and
                self.gap_policy == other.gap_policy and
                self.fold_policy == other.fold_policy)

    def __hash__(self):
        return hash((self.anchor, self.interval, self.invalid_date,
                     self.month_end, self.gap_policy, self.fold_policy))

    def _period_date(self, period):
        year, month = _split_month_index(
            (self.anchor.month - 1) + period * self.interval)
        year += self.anchor.year

        last_day = calendar.monthrange(year, month)[1]
        if self.month_end:
            day = last_day
        elif self.anchor.day > last_day:
            if self.invalid_date == SKIP:
                return None
            day = last_day
        else:
            day = self.anchor.day

        return datetime.date(year, month, day)

    def _apply_timezone(self, dt):
        aware = datetime.datetime.combine(dt, self.anchor.timetz())

        if aware.tzinfo is None:
            return aware

        if not datetime_exists(aware):
            if self.gap_policy == GAP_RAISE:
                raise ValueError("wall time %r does not exist in time zone "
                                 "%r" % (aware, aware.tzinfo))
            if self.gap_policy == GAP_SKIP:
                return None
            if self.gap_policy == GAP_FIRST:
                return resolve_imaginary(aware)
            return enfold(aware, fold=1).astimezone(aware.tzinfo)

        if datetime_ambiguous(aware):
            if self.fold_policy == FOLD_RAISE:
                raise ValueError("wall time %r is ambiguous in time zone "
                                 "%r" % (aware, aware.tzinfo))
            if self.fold_policy == FOLD_FIRST:
                return enfold(aware, fold=0)
            return enfold(aware, fold=1)

        return aware

    def get(self, period):
        """
        Return the occurrence for a period index.

        :param period:
            Integer period offset from the anchor; may be negative.

        :return:
            The same type as the anchor. With ``SKIP`` policies a missing
            period returns ``None``.
        """
        period = int(period)
        day = self._period_date(period)
        if day is None:
            return None

        if not isinstance(self.anchor, datetime.datetime):
            return day

        resolved = self._apply_timezone(day)
        if resolved is None:
            return None
        return resolved

    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.step == 0:
                raise ValueError("slice step cannot be zero")
            if index.stop is None:
                raise ValueError("an infinite anchored_calendar cannot be "
                                 "sliced without a stop index")
            if (index.start is not None and index.start < 0) or \
                    index.stop < 0:
                raise ValueError("an infinite anchored_calendar cannot be "
                                 "sliced with negative indices")
            return [self[i] for i in range(*index.indices(index.stop))]

        if self.invalid_date == SKIP or (
                isinstance(self.anchor, datetime.datetime) and
                self.gap_policy == GAP_SKIP):
            return self._nth_existing(index)

        value = self.get(index)
        if value is None:
            raise IndexError("period %r was skipped" % index)
        return value

    def _nth_existing(self, n):
        if n < 0:
            raise IndexError("cannot index a skip sequence from the end of "
                             "an infinite anchored_calendar")

        seen = 0
        period = 0
        while True:
            value = self.get(period)
            if value is not None:
                if seen == n:
                    return value
                seen += 1
            period += 1

    def __iter__(self):
        period = 0
        while True:
            value = self.get(period)
            if value is not None:
                yield value
            period += 1

    def __reversed__(self):
        period = 0
        while True:
            value = self.get(period)
            if value is not None:
                yield value
            period -= 1

    def take(self, count):
        """Return up to ``count`` occurrences starting at the anchor."""
        count = int(count)
        if count < 0:
            return [value for value, _ in zip(self.__reversed__(),
                                              range(-count))]
        return [value for value, _ in zip(self, range(count))]

    def between(self, start, end, *, inc_start=True, inc_end=True):
        """
        Return occurrences within a window.

        A reversed window (``start > end``) yields occurrences in reverse
        order, matching a negative ``interval``.

        :param start:
            Inclusive lower bound by default, as a date or datetime.

        :param end:
            Inclusive upper bound by default, as a date or datetime.

        :param inc_start:
            Set to ``False`` to exclude an occurrence equal to ``start``.

        :param inc_end:
            Set to ``False`` to exclude an occurrence equal to ``end``.
        """
        if not isinstance(start, datetime.date) or \
                not isinstance(end, datetime.date):
            raise TypeError("start and end must be datetime.date or "
                            "datetime.datetime instances")
        if isinstance(start, datetime.datetime) != \
                isinstance(end, datetime.datetime):
            raise TypeError("start and end must be the same kind of "
                            "datetime object")
        if isinstance(start, datetime.datetime) != \
                isinstance(self.anchor, datetime.datetime):
            raise TypeError("window bounds must match the anchor type")

        reverse = start > end
        if reverse:
            start, end = end, start

        results = []
        period = 0
        # The full supported date range spans fewer than 120,000 months.
        max_periods = 200000

        for _ in range(max_periods):
            value = self.get(period)
            if value is not None:
                within = start < value < end or \
                    (inc_start and value == start) or \
                    (inc_end and value == end)
                if within:
                    results.append(value)
                if self.interval > 0 and value > end:
                    break
                if self.interval < 0 and value < start:
                    break
            period += 1
        else:
            raise RuntimeError("window scan exceeded %d periods" %
                               max_periods)

        if reverse:
            results.reverse()
        return results
