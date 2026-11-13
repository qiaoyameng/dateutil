anchor
======
.. automodule:: dateutil.anchor
   :members:
   :undoc-members:

.. testsetup:: anchor

    >>> from datetime import date, datetime
    >>> from dateutil.anchor import anchored_calendar, SKIP

Why an anchored sequence?
-------------------------

Repeatedly adding :class:`dateutil.relativedelta.relativedelta` drifts when a
short month truncates the day of month, because each truncated result feeds
the next step:

.. doctest:: anchor

    >>> from dateutil.relativedelta import relativedelta
    >>> start = date(2023, 1, 31)
    >>> start + relativedelta(months=1)
    datetime.date(2023, 2, 28)
    >>> (start + relativedelta(months=1)) + relativedelta(months=1)
    datetime.date(2023, 3, 28)

An :class:`anchored_calendar` recomputes every period from the original
anchor instead, so March is back on the 31st:

.. doctest:: anchor

    >>> anchored_calendar(date(2023, 1, 31)).take(4)
    [datetime.date(2023, 1, 31), datetime.date(2023, 2, 28),
     datetime.date(2023, 3, 31), datetime.date(2023, 4, 30)]

Month-end versus fixed day of month
------------------------------------

An anchor on the last day of its month is treated as a month-end anchor by
default. Pass ``month_end=False`` to keep a fixed day of month instead, and
choose whether invalid dates are clamped or skipped:

.. doctest:: anchor

    >>> anchored_calendar(date(2023, 1, 31), month_end=True).take(3)
    [datetime.date(2023, 1, 31), datetime.date(2023, 2, 28),
     datetime.date(2023, 3, 31)]
    >>> anchored_calendar(date(2023, 1, 31), month_end=False).take(3)
    [datetime.date(2023, 1, 31), datetime.date(2023, 2, 28),
     datetime.date(2023, 3, 31)]
    >>> skip = anchored_calendar(date(2023, 1, 31), invalid_date=SKIP)
    >>> skip.get(1) is None
    True
    >>> skip.take(3)
    [datetime.date(2023, 1, 31), datetime.date(2023, 3, 31),
     datetime.date(2023, 5, 31)]

Intervals, iteration and windows
--------------------------------

Intervals may be larger than one month or negative, and sequences support
random access, finite counts and windowed queries:

.. doctest:: anchor

    >>> anchored_calendar(date(2023, 1, 31), interval=2).take(3)
    [datetime.date(2023, 1, 31), datetime.date(2023, 3, 31),
     datetime.date(2023, 5, 31)]
    >>> seq = anchored_calendar(date(2023, 1, 31))
    >>> seq[3]
    datetime.date(2023, 4, 30)
    >>> seq.between(date(2023, 2, 1), date(2023, 4, 1))
    [datetime.date(2023, 2, 28), datetime.date(2023, 3, 31)]

Time zones
----------

Aware datetimes keep their wall time and time zone. Wall times that fall in
a spring-forward gap or a fall-back fold are handled by explicit policies
built on :mod:`dateutil.tz`, rather than by silently shifting the result by
an hour.
