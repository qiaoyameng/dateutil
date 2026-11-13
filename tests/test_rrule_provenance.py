from datetime import datetime, timedelta

from dateutil import tz
from dateutil.rrule import DAILY, SECONDLY, rrule, rruleset


def _overlapping_set(reverse=False):
    start = datetime(2024, 1, 1, 9)
    first = rrule(DAILY, dtstart=start, count=5)
    second = rrule(DAILY, dtstart=start + timedelta(days=1), count=4)
    excluded_date = start + timedelta(days=2)
    rrset = rruleset()
    if reverse:
        rrset.exdate(excluded_date, id="excluded")
        rrset.rrule(second, id="second")
        rrset.rrule(first, id="first")
    else:
        rrset.rrule(first, id="first")
        rrset.rrule(second, id="second")
        rrset.exdate(excluded_date, id="excluded")
    return rrset, start


def test_provenance_for_overlapping_rules():
    rrset, start = _overlapping_set()
    result = rrset.between_with_provenance(
        start, start + timedelta(days=7))

    assert result.times == rrset.between(start, start + timedelta(days=7))

    excluded = result.excluded
    assert [item.dt for item in excluded] == [start + timedelta(days=2)]
    assert set(excluded[0].included_by_ids) == {"first", "second"}
    assert set(excluded[0].excluded_by_ids) == {"excluded"}
    assert not excluded[0].occurred

    overlapping = [item for item in result.occurrences
                   if item.sources == ("first", "second")]
    assert overlapping
    assert all(item.occurred for item in overlapping)


def test_provenance_is_add_order_independent():
    normal, start = _overlapping_set()
    reversed_set, _ = _overlapping_set(reverse=True)
    after = start
    before = start + timedelta(days=7)

    first = normal.between_with_provenance(after, before)
    second = reversed_set.between_with_provenance(after, before)

    assert first.times == normal.between(after, before)
    assert first.times == second.times
    assert (
        [(item.dt, item.sources, item.excluded_by_ids)
         for item in first.candidates]
        ==
        [(item.dt, item.sources, item.excluded_by_ids)
         for item in second.candidates]
    )


def test_provenance_separates_aware_and_floating():
    aware = rruleset()
    aware.rrule(
        rrule(DAILY,
              dtstart=datetime(2024, 1, 1, 9,
                               tzinfo=tz.tzoffset(None, 7200)),
              count=3),
        id="plus-two",
    )
    aware.rrule(
        rrule(DAILY,
              dtstart=datetime(2024, 1, 1, 7, tzinfo=tz.tzutc()),
              count=3),
        id="utc",
    )
    aware.rdate(datetime(2024, 1, 1, 9), id="floating")

    result = aware.between_with_provenance(
        datetime(2024, 1, 1, tzinfo=tz.tzutc()),
        datetime(2024, 1, 5, tzinfo=tz.tzutc()),
    )

    assert len(result.occurrences) == 3
    assert all(item.datetime.tzinfo is not None
               for item in result.occurrences)
    assert set(result.occurrences[0].sources) == {"plus-two", "utc"}

    floating = rruleset()
    floating.rrule(
        rrule(DAILY, dtstart=datetime(2024, 1, 1, 9), count=3),
        id="floating-rule",
    )
    floating.rdate(datetime(2024, 1, 2, 9), id="floating-date")
    floating_result = floating.between_with_provenance(
        datetime(2024, 1, 1), datetime(2024, 1, 5))
    assert all(item.datetime.tzinfo is None
               for item in floating_result.occurrences)
    assert "floating-date" in floating_result.occurrences[1].sources


def test_provenance_advances_only_through_window():
    start = datetime(2024, 1, 1, 9)
    rrset = rruleset()
    rrset.rrule(rrule(SECONDLY, dtstart=start), id="infinite")

    before = start + timedelta(seconds=3)
    result = rrset.between_with_provenance(start, before)

    assert result.times == rrset.between(start, before)
    assert result.times == [start + timedelta(seconds=1),
                            start + timedelta(seconds=2)]


def test_provenance_limits_do_not_change_occurrence_status():
    rrset, start = _overlapping_set()
    after = start
    before = start + timedelta(days=7)
    expected = rrset.between(after, before)

    evidence_limited = rrset.between_with_provenance(
        after, before, max_sources=0)
    assert evidence_limited.times == expected
    assert evidence_limited.sources_truncated
    assert all(item.included_by == []
               for item in evidence_limited.candidates)
    assert not evidence_limited.excluded[0].occurred

    diagnostic_limited = rrset.between_with_provenance(
        after, before, max_excluded=0)
    assert diagnostic_limited.times == expected
    assert diagnostic_limited.excluded == []
    assert diagnostic_limited.excluded_truncated
    assert diagnostic_limited.truncated


def test_between_keyword_returns_provenance_result():
    rrset, start = _overlapping_set()
    result = rrset.between(
        start, start + timedelta(days=7), with_sources=True)

    assert result.times == rrset.between(
        start, start + timedelta(days=7))
    assert result.excluded


def test_provenance_sources_survive_normal_iteration():
    start = datetime(2024, 1, 1, 9)
    rrset = rruleset()
    rrset.rrule(rrule(DAILY, dtstart=start, count=3), id="rule")
    rrset.rdate(start + timedelta(days=10), id="late-date")
    rrset.rdate(start + timedelta(days=5), id="early-date")
    rrset.exdate(start + timedelta(days=1), id="excluded")

    assert list(rrset)
    result = rrset.between_with_provenance(
        start, start + timedelta(days=6))

    by_dt = {item.dt: item for item in result.candidates}
    assert by_dt[start + timedelta(days=5)].sources == ("early-date",)
    assert by_dt[start + timedelta(days=1)].excluded_by_ids == ("excluded",)
