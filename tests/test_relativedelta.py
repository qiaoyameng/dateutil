# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from ._common import NotAValue

import calendar
from datetime import datetime, date, timedelta
import unittest

import pytest

from dateutil.relativedelta import (relativedelta, MO, TU, WE, FR, SU,
                                    DayResolution, MonthResolutionError)


class RelativeDeltaTest(unittest.TestCase):
    now = datetime(2003, 9, 17, 20, 54, 47, 282310)
    today = date(2003, 9, 17)

    def testInheritance(self):
        # Ensure that relativedelta is inheritance-friendly.
        class rdChildClass(relativedelta):
            pass

        ccRD = rdChildClass(years=1, months=1, days=1, leapdays=1, weeks=1,
                            hours=1, minutes=1, seconds=1, microseconds=1)

        rd = relativedelta(years=1, months=1, days=1, leapdays=1, weeks=1,
                           hours=1, minutes=1, seconds=1, microseconds=1)

        self.assertEqual(type(ccRD + rd), type(ccRD),
                         msg='Addition does not inherit type.')

        self.assertEqual(type(ccRD - rd), type(ccRD),
                         msg='Subtraction does not inherit type.')

        self.assertEqual(type(-ccRD), type(ccRD),
                         msg='Negation does not inherit type.')

        self.assertEqual(type(ccRD * 5.0), type(ccRD),
                         msg='Multiplication does not inherit type.')

        self.assertEqual(type(ccRD / 5.0), type(ccRD),
                         msg='Division does not inherit type.')

    def testMonthEndMonthBeginning(self):
        self.assertEqual(relativedelta(datetime(2003, 1, 31, 23, 59, 59),
                                       datetime(2003, 3, 1, 0, 0, 0)),
                         relativedelta(months=-1, seconds=-1))

        self.assertEqual(relativedelta(datetime(2003, 3, 1, 0, 0, 0),
                                       datetime(2003, 1, 31, 23, 59, 59)),
                         relativedelta(months=1, seconds=1))

    def testMonthEndMonthBeginningLeapYear(self):
        self.assertEqual(relativedelta(datetime(2012, 1, 31, 23, 59, 59),
                                       datetime(2012, 3, 1, 0, 0, 0)),
                         relativedelta(months=-1, seconds=-1))

        self.assertEqual(relativedelta(datetime(2003, 3, 1, 0, 0, 0),
                                       datetime(2003, 1, 31, 23, 59, 59)),
                         relativedelta(months=1, seconds=1))

    def testNextMonth(self):
        self.assertEqual(self.now+relativedelta(months=+1),
                         datetime(2003, 10, 17, 20, 54, 47, 282310))

    def testNextMonthPlusOneWeek(self):
        self.assertEqual(self.now+relativedelta(months=+1, weeks=+1),
                         datetime(2003, 10, 24, 20, 54, 47, 282310))

    def testNextMonthPlusOneWeek10am(self):
        self.assertEqual(self.today +
                         relativedelta(months=+1, weeks=+1, hour=10),
                         datetime(2003, 10, 24, 10, 0))

    def testNextMonthPlusOneWeek10amDiff(self):
        self.assertEqual(relativedelta(datetime(2003, 10, 24, 10, 0),
                                       self.today),
                         relativedelta(months=+1, days=+7, hours=+10))

    def testOneMonthBeforeOneYear(self):
        self.assertEqual(self.now+relativedelta(years=+1, months=-1),
                         datetime(2004, 8, 17, 20, 54, 47, 282310))

    def testMonthsOfDiffNumOfDays(self):
        self.assertEqual(date(2003, 1, 27)+relativedelta(months=+1),
                         date(2003, 2, 27))
        self.assertEqual(date(2003, 1, 31)+relativedelta(months=+1),
                         date(2003, 2, 28))
        self.assertEqual(date(2003, 1, 31)+relativedelta(months=+2),
                         date(2003, 3, 31))

    def testMonthsOfDiffNumOfDaysWithYears(self):
        self.assertEqual(date(2000, 2, 28)+relativedelta(years=+1),
                         date(2001, 2, 28))
        self.assertEqual(date(2000, 2, 29)+relativedelta(years=+1),
                         date(2001, 2, 28))

        self.assertEqual(date(1999, 2, 28)+relativedelta(years=+1),
                         date(2000, 2, 28))
        self.assertEqual(date(1999, 3, 1)+relativedelta(years=+1),
                         date(2000, 3, 1))
        self.assertEqual(date(1999, 3, 1)+relativedelta(years=+1),
                         date(2000, 3, 1))

        self.assertEqual(date(2001, 2, 28)+relativedelta(years=-1),
                         date(2000, 2, 28))
        self.assertEqual(date(2001, 3, 1)+relativedelta(years=-1),
                         date(2000, 3, 1))

    def testNextFriday(self):
        self.assertEqual(self.today+relativedelta(weekday=FR),
                         date(2003, 9, 19))

    def testNextFridayInt(self):
        self.assertEqual(self.today+relativedelta(weekday=calendar.FRIDAY),
                         date(2003, 9, 19))

    def testLastFridayInThisMonth(self):
        self.assertEqual(self.today+relativedelta(day=31, weekday=FR(-1)),
                         date(2003, 9, 26))

    def testLastDayOfFebruary(self):
        self.assertEqual(date(2021, 2, 1) + relativedelta(day=31),
                         date(2021, 2, 28))

    def testLastDayOfFebruaryLeapYear(self):
        self.assertEqual(date(2020, 2, 1) + relativedelta(day=31),
                         date(2020, 2, 29))

    def testNextWednesdayIsToday(self):
        self.assertEqual(self.today+relativedelta(weekday=WE),
                         date(2003, 9, 17))

    def testNextWednesdayNotToday(self):
        self.assertEqual(self.today+relativedelta(days=+1, weekday=WE),
                         date(2003, 9, 24))

    def testAddMoreThan12Months(self):
        self.assertEqual(date(2003, 12, 1) + relativedelta(months=+13),
                         date(2005, 1, 1))

    def testAddNegativeMonths(self):
        self.assertEqual(date(2003, 1, 1) + relativedelta(months=-2),
                         date(2002, 11, 1))

    def test15thISOYearWeek(self):
        self.assertEqual(date(2003, 1, 1) +
                         relativedelta(day=4, weeks=+14, weekday=MO(-1)),
                         date(2003, 4, 7))

    def testMillenniumAge(self):
        self.assertEqual(relativedelta(self.now, date(2001, 1, 1)),
                         relativedelta(years=+2, months=+8, days=+16,
                                       hours=+20, minutes=+54, seconds=+47,
                                       microseconds=+282310))

    def testJohnAge(self):
        self.assertEqual(relativedelta(self.now,
                                       datetime(1978, 4, 5, 12, 0)),
                         relativedelta(years=+25, months=+5, days=+12,
                                       hours=+8, minutes=+54, seconds=+47,
                                       microseconds=+282310))

    def testJohnAgeWithDate(self):
        self.assertEqual(relativedelta(self.today,
                                       datetime(1978, 4, 5, 12, 0)),
                         relativedelta(years=+25, months=+5, days=+11,
                                       hours=+12))

    def testYearDay(self):
        self.assertEqual(date(2003, 1, 1)+relativedelta(yearday=260),
                         date(2003, 9, 17))
        self.assertEqual(date(2002, 1, 1)+relativedelta(yearday=260),
                         date(2002, 9, 17))
        self.assertEqual(date(2000, 1, 1)+relativedelta(yearday=260),
                         date(2000, 9, 16))
        self.assertEqual(self.today+relativedelta(yearday=261),
                         date(2003, 9, 18))

    def testYearDayBug(self):
        # Tests a problem reported by Adam Ryan.
        self.assertEqual(date(2010, 1, 1)+relativedelta(yearday=15),
                         date(2010, 1, 15))

    def testNonLeapYearDay(self):
        self.assertEqual(date(2003, 1, 1)+relativedelta(nlyearday=260),
                         date(2003, 9, 17))
        self.assertEqual(date(2002, 1, 1)+relativedelta(nlyearday=260),
                         date(2002, 9, 17))
        self.assertEqual(date(2000, 1, 1)+relativedelta(nlyearday=260),
                         date(2000, 9, 17))
        self.assertEqual(self.today+relativedelta(yearday=261),
                         date(2003, 9, 18))

    def testAddition(self):
        self.assertEqual(relativedelta(days=10) +
                         relativedelta(years=1, months=2, days=3, hours=4,
                                       minutes=5, microseconds=6),
                         relativedelta(years=1, months=2, days=13, hours=4,
                                       minutes=5, microseconds=6))

    def testAbsoluteAddition(self):
        self.assertEqual(relativedelta() + relativedelta(day=0, hour=0),
                         relativedelta(day=0, hour=0))
        self.assertEqual(relativedelta(day=0, hour=0) + relativedelta(),
                         relativedelta(day=0, hour=0))

    def testAdditionToDatetime(self):
        self.assertEqual(datetime(2000, 1, 1) + relativedelta(days=1),
                         datetime(2000, 1, 2))

    def testRightAdditionToDatetime(self):
        self.assertEqual(relativedelta(days=1) + datetime(2000, 1, 1),
                         datetime(2000, 1, 2))

    def testAdditionInvalidType(self):
        with self.assertRaises(TypeError):
            relativedelta(days=3) + 9

    def testAdditionUnsupportedType(self):
        # For unsupported types that define their own comparators, etc.
        self.assertIs(relativedelta(days=1) + NotAValue, NotAValue)

    def testAdditionFloatValue(self):
        self.assertEqual(datetime(2000, 1, 1) + relativedelta(days=float(1)),
                         datetime(2000, 1, 2))
        self.assertEqual(datetime(2000, 1, 1) + relativedelta(months=float(1)),
                         datetime(2000, 2, 1))
        self.assertEqual(datetime(2000, 1, 1) + relativedelta(years=float(1)),
                         datetime(2001, 1, 1))

    def testAdditionFloatFractionals(self):
        self.assertEqual(datetime(2000, 1, 1, 0) +
                         relativedelta(days=float(0.5)),
                         datetime(2000, 1, 1, 12))
        self.assertEqual(datetime(2000, 1, 1, 0, 0) +
                         relativedelta(hours=float(0.5)),
                         datetime(2000, 1, 1, 0, 30))
        self.assertEqual(datetime(2000, 1, 1, 0, 0, 0) +
                         relativedelta(minutes=float(0.5)),
                         datetime(2000, 1, 1, 0, 0, 30))
        self.assertEqual(datetime(2000, 1, 1, 0, 0, 0, 0) +
                         relativedelta(seconds=float(0.5)),
                         datetime(2000, 1, 1, 0, 0, 0, 500000))
        self.assertEqual(datetime(2000, 1, 1, 0, 0, 0, 0) +
                         relativedelta(microseconds=float(500000.25)),
                         datetime(2000, 1, 1, 0, 0, 0, 500000))

    def testSubtraction(self):
        self.assertEqual(relativedelta(days=10) -
                         relativedelta(years=1, months=2, days=3, hours=4,
                                       minutes=5, microseconds=6),
                         relativedelta(years=-1, months=-2, days=7, hours=-4,
                                       minutes=-5, microseconds=-6))

    def testRightSubtractionFromDatetime(self):
        self.assertEqual(datetime(2000, 1, 2) - relativedelta(days=1),
                         datetime(2000, 1, 1))

    def testSubractionWithDatetime(self):
        self.assertRaises(TypeError, lambda x, y: x - y,
                          (relativedelta(days=1), datetime(2000, 1, 1)))

    def testSubtractionInvalidType(self):
        with self.assertRaises(TypeError):
            relativedelta(hours=12) - 14

    def testSubtractionUnsupportedType(self):
        self.assertIs(relativedelta(days=1) + NotAValue, NotAValue)

    def testMultiplication(self):
        self.assertEqual(datetime(2000, 1, 1) + relativedelta(days=1) * 28,
                         datetime(2000, 1, 29))
        self.assertEqual(datetime(2000, 1, 1) + 28 * relativedelta(days=1),
                         datetime(2000, 1, 29))

    def testMultiplicationUnsupportedType(self):
        self.assertIs(relativedelta(days=1) * NotAValue, NotAValue)

    def testDivision(self):
        self.assertEqual(datetime(2000, 1, 1) + relativedelta(days=28) / 28,
                         datetime(2000, 1, 2))

    def testDivisionUnsupportedType(self):
        self.assertIs(relativedelta(days=1) / NotAValue, NotAValue)

    def testBoolean(self):
        self.assertFalse(relativedelta(days=0))
        self.assertTrue(relativedelta(days=1))

    def testAbsoluteValueNegative(self):
        rd_base = relativedelta(years=-1, months=-5, days=-2, hours=-3,
                                minutes=-5, seconds=-2, microseconds=-12)
        rd_expected = relativedelta(years=1, months=5, days=2, hours=3,
                                    minutes=5, seconds=2, microseconds=12)
        self.assertEqual(abs(rd_base), rd_expected)

    def testAbsoluteValuePositive(self):
        rd_base = relativedelta(years=1, months=5, days=2, hours=3,
                                minutes=5, seconds=2, microseconds=12)
        rd_expected = rd_base

        self.assertEqual(abs(rd_base), rd_expected)

    def testComparison(self):
        d1 = relativedelta(years=1, months=1, days=1, leapdays=0, hours=1,
                           minutes=1, seconds=1, microseconds=1)
        d2 = relativedelta(years=1, months=1, days=1, leapdays=0, hours=1,
                           minutes=1, seconds=1, microseconds=1)
        d3 = relativedelta(years=1, months=1, days=1, leapdays=0, hours=1,
                           minutes=1, seconds=1, microseconds=2)

        self.assertEqual(d1, d2)
        self.assertNotEqual(d1, d3)

    def testInequalityTypeMismatch(self):
        # Different type
        self.assertFalse(relativedelta(year=1) == 19)

    def testInequalityUnsupportedType(self):
        self.assertIs(relativedelta(hours=3) == NotAValue, NotAValue)

    def testInequalityWeekdays(self):
        # Different weekdays
        no_wday = relativedelta(year=1997, month=4)
        wday_mo_1 = relativedelta(year=1997, month=4, weekday=MO(+1))
        wday_mo_2 = relativedelta(year=1997, month=4, weekday=MO(+2))
        wday_tu = relativedelta(year=1997, month=4, weekday=TU)

        self.assertTrue(wday_mo_1 == wday_mo_1)

        self.assertFalse(no_wday == wday_mo_1)
        self.assertFalse(wday_mo_1 == no_wday)

        self.assertFalse(wday_mo_1 == wday_mo_2)
        self.assertFalse(wday_mo_2 == wday_mo_1)

        self.assertFalse(wday_mo_1 == wday_tu)
        self.assertFalse(wday_tu == wday_mo_1)

    def testMonthOverflow(self):
        self.assertEqual(relativedelta(months=273),
                         relativedelta(years=22, months=9))

    def testWeeks(self):
        # Test that the weeks property is working properly.
        rd = relativedelta(years=4, months=2, weeks=8, days=6)
        self.assertEqual((rd.weeks, rd.days), (8, 8 * 7 + 6))

        rd.weeks = 3
        self.assertEqual((rd.weeks, rd.days), (3, 3 * 7 + 6))

    def testRelativeDeltaRepr(self):
        self.assertEqual(repr(relativedelta(years=1, months=-1, days=15)),
                         'relativedelta(years=+1, months=-1, days=+15)')

        self.assertEqual(repr(relativedelta(months=14, seconds=-25)),
                         'relativedelta(years=+1, months=+2, seconds=-25)')

        self.assertEqual(repr(relativedelta(month=3, hour=3, weekday=SU(3))),
                         'relativedelta(month=3, weekday=SU(+3), hour=3)')

    def testRelativeDeltaFractionalYear(self):
        with self.assertRaises(ValueError):
            relativedelta(years=1.5)

    def testRelativeDeltaFractionalMonth(self):
        with self.assertRaises(ValueError):
            relativedelta(months=1.5)

    def testRelativeDeltaInvalidDatetimeObject(self):
        with self.assertRaises(TypeError):
            relativedelta(dt1='2018-01-01', dt2='2018-01-02')

        with self.assertRaises(TypeError):
            relativedelta(dt1=datetime(2018, 1, 1), dt2='2018-01-02')

        with self.assertRaises(TypeError):
            relativedelta(dt1='2018-01-01', dt2=datetime(2018, 1, 2))

    def testRelativeDeltaFractionalAbsolutes(self):
        # Fractional absolute values will soon be unsupported,
        # check for the deprecation warning.
        with pytest.warns(DeprecationWarning):
            relativedelta(year=2.86)

        with pytest.warns(DeprecationWarning):
            relativedelta(month=1.29)

        with pytest.warns(DeprecationWarning):
            relativedelta(day=0.44)

        with pytest.warns(DeprecationWarning):
            relativedelta(hour=23.98)

        with pytest.warns(DeprecationWarning):
            relativedelta(minute=45.21)

        with pytest.warns(DeprecationWarning):
            relativedelta(second=13.2)

        with pytest.warns(DeprecationWarning):
            relativedelta(microsecond=157221.93)

    def testRelativeDeltaFractionalRepr(self):
        rd = relativedelta(years=3, months=-2, days=1.25)

        self.assertEqual(repr(rd),
                         'relativedelta(years=+3, months=-2, days=+1.25)')

        rd = relativedelta(hours=0.5, seconds=9.22)
        self.assertEqual(repr(rd),
                         'relativedelta(hours=+0.5, seconds=+9.22)')

    def testRelativeDeltaFractionalWeeks(self):
        # Equivalent to days=8, hours=18
        rd = relativedelta(weeks=1.25)
        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd,
                         datetime(2009, 9, 11, 18))

    def testRelativeDeltaFractionalDays(self):
        rd1 = relativedelta(days=1.48)

        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd1,
                         datetime(2009, 9, 4, 11, 31, 12))

        rd2 = relativedelta(days=1.5)
        self.assertEqual(d1 + rd2,
                         datetime(2009, 9, 4, 12, 0, 0))

    def testRelativeDeltaFractionalHours(self):
        rd = relativedelta(days=1, hours=12.5)
        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd,
                         datetime(2009, 9, 4, 12, 30, 0))

    def testRelativeDeltaFractionalMinutes(self):
        rd = relativedelta(hours=1, minutes=30.5)
        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd,
                         datetime(2009, 9, 3, 1, 30, 30))

    def testRelativeDeltaFractionalSeconds(self):
        rd = relativedelta(hours=5, minutes=30, seconds=30.5)
        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd,
                         datetime(2009, 9, 3, 5, 30, 30, 500000))

    def testRelativeDeltaFractionalPositiveOverflow(self):
        # Equivalent to (days=1, hours=14)
        rd1 = relativedelta(days=1.5, hours=2)
        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd1,
                         datetime(2009, 9, 4, 14, 0, 0))

        # Equivalent to (days=1, hours=14, minutes=45)
        rd2 = relativedelta(days=1.5, hours=2.5, minutes=15)
        d1 = datetime(2009, 9, 3, 0, 0)
        self.assertEqual(d1 + rd2,
                         datetime(2009, 9, 4, 14, 45))

        # Carry back up - equivalent to (days=2, hours=2, minutes=0, seconds=1)
        rd3 = relativedelta(days=1.5, hours=13, minutes=59.5, seconds=31)
        self.assertEqual(d1 + rd3,
                         datetime(2009, 9, 5, 2, 0, 1))

    def testRelativeDeltaFractionalNegativeDays(self):
        # Equivalent to (days=-1, hours=-1)
        rd1 = relativedelta(days=-1.5, hours=11)
        d1 = datetime(2009, 9, 3, 12, 0)
        self.assertEqual(d1 + rd1,
                         datetime(2009, 9, 2, 11, 0, 0))

        # Equivalent to (days=-1, hours=-9)
        rd2 = relativedelta(days=-1.25, hours=-3)
        self.assertEqual(d1 + rd2,
            datetime(2009, 9, 2, 3))

    def testRelativeDeltaNormalizeFractionalDays(self):
        # Equivalent to (days=2, hours=18)
        rd1 = relativedelta(days=2.75)

        self.assertEqual(rd1.normalized(), relativedelta(days=2, hours=18))

        # Equivalent to (days=1, hours=11, minutes=31, seconds=12)
        rd2 = relativedelta(days=1.48)

        self.assertEqual(rd2.normalized(),
            relativedelta(days=1, hours=11, minutes=31, seconds=12))

    def testRelativeDeltaNormalizeFractionalDays2(self):
        # Equivalent to (hours=1, minutes=30)
        rd1 = relativedelta(hours=1.5)

        self.assertEqual(rd1.normalized(), relativedelta(hours=1, minutes=30))

        # Equivalent to (hours=3, minutes=17, seconds=5, microseconds=100)
        rd2 = relativedelta(hours=3.28472225)

        self.assertEqual(rd2.normalized(),
            relativedelta(hours=3, minutes=17, seconds=5, microseconds=100))

    def testRelativeDeltaNormalizeFractionalMinutes(self):
        # Equivalent to (minutes=15, seconds=36)
        rd1 = relativedelta(minutes=15.6)

        self.assertEqual(rd1.normalized(),
            relativedelta(minutes=15, seconds=36))

        # Equivalent to (minutes=25, seconds=20, microseconds=25000)
        rd2 = relativedelta(minutes=25.33375)

        self.assertEqual(rd2.normalized(),
            relativedelta(minutes=25, seconds=20, microseconds=25000))

    def testRelativeDeltaNormalizeFractionalSeconds(self):
        # Equivalent to (seconds=45, microseconds=25000)
        rd1 = relativedelta(seconds=45.025)
        self.assertEqual(rd1.normalized(),
            relativedelta(seconds=45, microseconds=25000))

    def testRelativeDeltaFractionalPositiveOverflow2(self):
        # Equivalent to (days=1, hours=14)
        rd1 = relativedelta(days=1.5, hours=2)
        self.assertEqual(rd1.normalized(),
            relativedelta(days=1, hours=14))

        # Equivalent to (days=1, hours=14, minutes=45)
        rd2 = relativedelta(days=1.5, hours=2.5, minutes=15)
        self.assertEqual(rd2.normalized(),
            relativedelta(days=1, hours=14, minutes=45))

        # Carry back up - equivalent to:
        # (days=2, hours=2, minutes=0, seconds=2, microseconds=3)
        rd3 = relativedelta(days=1.5, hours=13, minutes=59.50045,
                            seconds=31.473, microseconds=500003)
        self.assertEqual(rd3.normalized(),
            relativedelta(days=2, hours=2, minutes=0,
                          seconds=2, microseconds=3))

    def testRelativeDeltaFractionalNegativeOverflow(self):
        # Equivalent to (days=-1)
        rd1 = relativedelta(days=-0.5, hours=-12)
        self.assertEqual(rd1.normalized(),
            relativedelta(days=-1))

        # Equivalent to (days=-1)
        rd2 = relativedelta(days=-1.5, hours=12)
        self.assertEqual(rd2.normalized(),
            relativedelta(days=-1))

        # Equivalent to (days=-1, hours=-14, minutes=-45)
        rd3 = relativedelta(days=-1.5, hours=-2.5, minutes=-15)
        self.assertEqual(rd3.normalized(),
            relativedelta(days=-1, hours=-14, minutes=-45))

        # Equivalent to (days=-1, hours=-14, minutes=+15)
        rd4 = relativedelta(days=-1.5, hours=-2.5, minutes=45)
        self.assertEqual(rd4.normalized(),
            relativedelta(days=-1, hours=-14, minutes=+15))

        # Carry back up - equivalent to:
        # (days=-2, hours=-2, minutes=0, seconds=-2, microseconds=-3)
        rd3 = relativedelta(days=-1.5, hours=-13, minutes=-59.50045,
                            seconds=-31.473, microseconds=-500003)
        self.assertEqual(rd3.normalized(),
            relativedelta(days=-2, hours=-2, minutes=0,
                          seconds=-2, microseconds=-3))

    def testInvalidYearDay(self):
        with self.assertRaises(ValueError):
            relativedelta(yearday=367)

    def testAddTimedeltaToUnpopulatedRelativedelta(self):
        td = timedelta(
            days=1,
            seconds=1,
            microseconds=1,
            milliseconds=1,
            minutes=1,
            hours=1,
            weeks=1
        )

        expected = relativedelta(
            weeks=1,
            days=1,
            hours=1,
            minutes=1,
            seconds=1,
            microseconds=1001
        )

        self.assertEqual(expected, relativedelta() + td)

    def testAddTimedeltaToPopulatedRelativeDelta(self):
        td = timedelta(
            days=1,
            seconds=1,
            microseconds=1,
            milliseconds=1,
            minutes=1,
            hours=1,
            weeks=1
        )

        rd = relativedelta(
            year=1,
            month=1,
            day=1,
            hour=1,
            minute=1,
            second=1,
            microsecond=1,
            years=1,
            months=1,
            days=1,
            weeks=1,
            hours=1,
            minutes=1,
            seconds=1,
            microseconds=1
        )

        expected = relativedelta(
            year=1,
            month=1,
            day=1,
            hour=1,
            minute=1,
            second=1,
            microsecond=1,
            years=1,
            months=1,
            weeks=2,
            days=2,
            hours=2,
            minutes=2,
            seconds=2,
            microseconds=1002,
        )

        self.assertEqual(expected, rd + td)

    def testHashable(self):
        try:
            {relativedelta(minute=1): 'test'}
        except:
            self.fail("relativedelta() failed to hash!")

    def testDayOfMonthPlus(self):
        assert [
            date(2021, 1, 28) + relativedelta(months=1),
            date(2021, 2, 27) + relativedelta(months=1),
            date(2021, 4, 29) + relativedelta(months=1),
            date(2021, 5, 30) + relativedelta(months=1),
        ] == [
            date(2021, 2, 28),
            date(2021, 3, 27),
            date(2021, 5, 29),
            date(2021, 6, 30),
        ]

    def testLastDayOfMonthPlus(self):
        assert [
            date(2021, 1, 31) + relativedelta(months=1),
            date(2021, 1, 30) + relativedelta(months=1),
            date(2021, 1, 29) + relativedelta(months=1),
            date(2021, 1, 28) + relativedelta(months=1),
            date(2021, 2, 28) + relativedelta(months=1),
            date(2021, 4, 30) + relativedelta(months=1),
            date(2021, 5, 31) + relativedelta(months=1),
        ] == [
            date(2021, 2, 28),
            date(2021, 2, 28),
            date(2021, 2, 28),
            date(2021, 2, 28),
            date(2021, 3, 28),
            date(2021, 5, 30),
            date(2021, 6, 30),
        ]

    def testDayOfMonthMinus(self):
        assert [
           date(2021, 2, 27) - relativedelta(months=1),
           date(2021, 3, 30) - relativedelta(months=1),
           date(2021, 3, 29) - relativedelta(months=1),
           date(2021, 3, 28) - relativedelta(months=1),
           date(2021, 5, 30) - relativedelta(months=1),
           date(2021, 6, 29) - relativedelta(months=1),
        ] == [
            date(2021, 1, 27),
            date(2021, 2, 28),
            date(2021, 2, 28),
            date(2021, 2, 28),
            date(2021, 4, 30),
            date(2021, 5, 29),
        ]

    def testLastDayOfMonthMinus(self):
        assert [
            date(2021, 2, 28) - relativedelta(months=1),
            date(2021, 3, 31) - relativedelta(months=1),
            date(2021, 5, 31) - relativedelta(months=1),
            date(2021, 6, 30) - relativedelta(months=1),
        ] == [
            date(2021, 1, 28),
            date(2021, 2, 28),
            date(2021, 4, 30),
            date(2021, 5, 30),
        ]

class RelativeDeltaWeeksPropertyGetterTest(unittest.TestCase):
    """Test the weeks property getter"""

    def test_one_day(self):
        rd = relativedelta(days=1)
        self.assertEqual(rd.days, 1)
        self.assertEqual(rd.weeks, 0)

    def test_minus_one_day(self):
        rd = relativedelta(days=-1)
        self.assertEqual(rd.days, -1)
        self.assertEqual(rd.weeks, 0)

    def test_height_days(self):
        rd = relativedelta(days=8)
        self.assertEqual(rd.days, 8)
        self.assertEqual(rd.weeks, 1)

    def test_minus_height_days(self):
        rd = relativedelta(days=-8)
        self.assertEqual(rd.days, -8)
        self.assertEqual(rd.weeks, -1)


class RelativeDeltaWeeksPropertySetterTest(unittest.TestCase):
    """Test the weeks setter which makes a "smart" update of the days attribute"""

    def test_one_day_set_one_week(self):
        rd = relativedelta(days=1)
        rd.weeks = 1  # add 7 days
        self.assertEqual(rd.days, 8)
        self.assertEqual(rd.weeks, 1)

    def test_minus_one_day_set_one_week(self):
        rd = relativedelta(days=-1)
        rd.weeks = 1  # add 7 days
        self.assertEqual(rd.days, 6)
        self.assertEqual(rd.weeks, 0)

    def test_height_days_set_minus_one_week(self):
        rd = relativedelta(days=8)
        rd.weeks = -1  # change from 1 week, 1 day to -1 week, 1 day
        self.assertEqual(rd.days, -6)
        self.assertEqual(rd.weeks, 0)

    def test_minus_height_days_set_minus_one_week(self):
        rd = relativedelta(days=-8)
        rd.weeks = -1  # does not change anything
        self.assertEqual(rd.days, -8)
        self.assertEqual(rd.weeks, -1)


class DayResolutionTest(unittest.TestCase):
    """Tests for the explicit calendar-arithmetic strategies applied when
    the target day does not exist in the target month."""
    jan31_leap = date(2020, 1, 31)
    jan31_common = date(2019, 1, 31)

    def test_default_is_last_day(self):
        rd = relativedelta(months=1)
        self.assertEqual(rd.day_resolution, DayResolution.LAST_DAY)
        self.assertEqual(self.jan31_leap + rd, date(2020, 2, 29))
        self.assertEqual(self.jan31_common + relativedelta(months=1),
                         date(2019, 2, 28))

    def test_explicit_last_day_matches_default(self):
        rd = relativedelta(months=1,
                           day_resolution=DayResolution.LAST_DAY)
        self.assertEqual(self.jan31_leap + rd,
                         self.jan31_leap + relativedelta(months=1))

    def test_overflow_common_and_leap_year(self):
        rd = relativedelta(months=1,
                           day_resolution=DayResolution.OVERFLOW)
        self.assertEqual(self.jan31_leap + rd, date(2020, 3, 2))
        self.assertEqual(self.jan31_common + rd, date(2019, 3, 3))

    def test_raise_on_missing_day(self):
        with self.assertRaises(MonthResolutionError) as cm:
            self.jan31_leap + relativedelta(
                months=1, day_resolution=DayResolution.RAISE)
        exc = cm.exception
        self.assertIsInstance(exc, ValueError)
        self.assertIs(exc.original, self.jan31_leap)
        self.assertEqual((exc.year, exc.month, exc.day, exc.max_day),
                         (2020, 2, 31, 29))

    def test_raise_does_not_trigger_when_day_exists(self):
        result = date(2020, 1, 15) + relativedelta(
            months=1, day_resolution=DayResolution.RAISE)
        self.assertEqual(result, date(2020, 2, 15))

    def test_leap_day_plus_one_year(self):
        feb29 = date(2020, 2, 29)
        self.assertEqual(feb29 + relativedelta(years=1), date(2021, 2, 28))
        self.assertEqual(
            feb29 + relativedelta(
                years=1, day_resolution=DayResolution.OVERFLOW),
            date(2021, 3, 1))
        with self.assertRaises(MonthResolutionError):
            feb29 + relativedelta(years=1,
                                  day_resolution=DayResolution.RAISE)

    def test_negative_months(self):
        self.assertEqual(date(2020, 3, 31) + relativedelta(months=-1),
                         date(2020, 2, 29))
        self.assertEqual(
            date(2020, 3, 31) + relativedelta(
                months=-1, day_resolution=DayResolution.OVERFLOW),
            date(2020, 3, 2))
        with self.assertRaises(MonthResolutionError) as cm:
            date(2020, 10, 31) + relativedelta(
                months=-1, day_resolution=DayResolution.RAISE)
        self.assertEqual(
            (cm.exception.year, cm.exception.month, cm.exception.max_day),
            (2020, 9, 30))
        # Spilling always walks forward on the calendar.
        self.assertEqual(
            date(2020, 10, 31) + relativedelta(
                months=-1, day_resolution=DayResolution.OVERFLOW),
            date(2020, 10, 1))

    def test_two_single_steps_differ_from_one_double_step(self):
        # The deltas must be applied one at a time, never pre-merged.
        overflow = relativedelta(
            months=1, day_resolution=DayResolution.OVERFLOW)
        self.assertEqual(self.jan31_leap + overflow + overflow,
                         date(2020, 4, 2))
        self.assertEqual(
            self.jan31_leap + relativedelta(
                months=2, day_resolution=DayResolution.OVERFLOW),
            date(2020, 3, 31))
        # Historical clamping behavior shows the same kind of difference.
        self.assertEqual(
            self.jan31_leap + relativedelta(months=1)
            + relativedelta(months=1),
            date(2020, 3, 29))
        self.assertEqual(self.jan31_leap + relativedelta(months=2),
                         date(2020, 3, 31))

    def test_absolute_day_resolution(self):
        self.assertEqual(date(2020, 2, 10) + relativedelta(day=31),
                         date(2020, 2, 29))
        self.assertEqual(
            date(2020, 2, 10) + relativedelta(
                day=31, day_resolution=DayResolution.OVERFLOW),
            date(2020, 3, 2))
        with self.assertRaises(MonthResolutionError) as cm:
            date(2020, 2, 10) + relativedelta(
                day=31, day_resolution=DayResolution.RAISE)
        self.assertEqual(cm.exception.original, date(2020, 2, 10))

    def test_weekday_is_applied_after_day_resolution(self):
        overflow = dict(day_resolution=DayResolution.OVERFLOW)
        # Jan 31 + 1 month overflows to Monday 2020-03-02.
        self.assertEqual(
            self.jan31_leap + relativedelta(months=1, weekday=MO(1),
                                            **overflow),
            date(2020, 3, 2))
        self.assertEqual(
            self.jan31_leap + relativedelta(months=1, weekday=SU(1),
                                            **overflow),
            date(2020, 3, 8))
        # Clamped Feb 29 2020 is a Saturday; first Monday is March 2.
        self.assertEqual(
            self.jan31_leap + relativedelta(months=1, weekday=MO(1)),
            date(2020, 3, 2))

    def test_relative_days_added_after_resolution(self):
        self.assertEqual(
            self.jan31_leap + relativedelta(months=1, days=2),
            date(2020, 3, 2))
        self.assertEqual(
            self.jan31_leap + relativedelta(
                months=1, days=2, day_resolution=DayResolution.OVERFLOW),
            date(2020, 3, 4))

    def test_overflow_with_absolute_time_components(self):
        result = datetime(2020, 1, 31, 9, 30) + relativedelta(
            months=1, hour=12, day_resolution=DayResolution.OVERFLOW)
        # Only the hour is replaced; the original minute is kept.
        self.assertEqual(result, datetime(2020, 3, 2, 12, 30))

    def test_overflow_combined_with_timedelta_keeps_strategy(self):
        rd = relativedelta(months=1,
                           day_resolution=DayResolution.OVERFLOW)
        combined = rd + timedelta(days=5)
        self.assertEqual(combined.day_resolution,
                         DayResolution.OVERFLOW)
        self.assertEqual(self.jan31_leap + combined, date(2020, 3, 7))

    def test_invalid_day_resolution(self):
        with self.assertRaises(ValueError):
            relativedelta(months=1, day_resolution="nonsense")

    def test_strategy_propagates_through_operations(self):
        overflow = relativedelta(
            months=1, day_resolution=DayResolution.OVERFLOW)
        self.assertEqual((-overflow).day_resolution,
                         DayResolution.OVERFLOW)
        self.assertEqual((overflow + relativedelta(days=3)).day_resolution,
                         DayResolution.OVERFLOW)
        self.assertEqual(
            (relativedelta(months=1)
             + relativedelta(days=1, day_resolution=DayResolution.RAISE))
            .day_resolution,
            DayResolution.RAISE)

    def test_equality_hash_and_repr(self):
        overflow = relativedelta(
            months=1, day_resolution=DayResolution.OVERFLOW)
        self.assertNotEqual(overflow, relativedelta(months=1))
        self.assertEqual(
            hash(overflow),
            hash(relativedelta(months=1,
                               day_resolution=DayResolution.OVERFLOW)))
        self.assertIn("day_resolution='overflow'", repr(overflow))
        self.assertEqual(repr(relativedelta(months=1)),
                         "relativedelta(months=+1)")

    @pytest.mark.gettz
    def test_timezone_aware_datetime_preserved(self):
        from dateutil.tz import gettz
        nyc = gettz("America/New_York")
        dt = datetime(2020, 1, 31, 12, 0, tzinfo=nyc)
        overflow = dt + relativedelta(
            months=1, day_resolution=DayResolution.OVERFLOW)
        self.assertEqual(overflow,
                         datetime(2020, 3, 2, 12, 0, tzinfo=nyc))
        self.assertIs(overflow.tzinfo, dt.tzinfo)
        clamped = dt + relativedelta(months=1)
        self.assertEqual(clamped,
                         datetime(2020, 2, 29, 12, 0, tzinfo=nyc))
        with self.assertRaises(MonthResolutionError) as cm:
            dt + relativedelta(months=1,
                               day_resolution=DayResolution.RAISE)
        self.assertEqual(cm.exception.original, dt)


# vim:ts=4:sw=4:et
