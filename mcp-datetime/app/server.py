"""MCP server exposing date, time and period utilities."""

import calendar
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

from app.auth import AuthSettings, BearerAuthMiddleware

mcp = MCPServer("datetime", instructions="Date, time-zone and period calculations. Dates are ISO 8601.")

Unit = Literal["days", "weeks", "months", "years"]
PeriodKind = Literal["week", "month", "quarter", "year"]


def _add_months(d: date, months: int) -> date:
    index = d.year * 12 + d.month - 1 + months
    year, month = divmod(index, 12)
    return d.replace(year=year, month=month + 1, day=min(d.day, calendar.monthrange(year, month + 1)[1]))


def _shift(d: date, amount: int, unit: Unit) -> date:
    match unit:
        case "days":
            return d + timedelta(days=amount)
        case "weeks":
            return d + timedelta(weeks=amount)
        case "months":
            return _add_months(d, amount)
        case "years":
            return _add_months(d, amount * 12)


@mcp.tool()
def now(timezone: str = "UTC") -> dict:
    """Current date and time in an IANA time zone (e.g. Europe/Paris)."""
    current = datetime.now(ZoneInfo(timezone))
    return {
        "iso": current.isoformat(),
        "date": current.date().isoformat(),
        "weekday": calendar.day_name[current.weekday()],
        "timezone": timezone,
    }


@mcp.tool()
def convert_timezone(datetime_iso: str, from_timezone: str, to_timezone: str) -> str:
    """Convert an ISO datetime to another time zone. Naive datetimes are read in `from_timezone`."""
    parsed = datetime.fromisoformat(datetime_iso)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(from_timezone))
    return parsed.astimezone(ZoneInfo(to_timezone)).isoformat()


@mcp.tool()
def add_to_date(date_iso: str, amount: int, unit: Unit) -> str:
    """Add (or subtract, with a negative amount) days, weeks, months or years. Month ends are clamped."""
    return _shift(date.fromisoformat(date_iso), amount, unit).isoformat()


@mcp.tool()
def date_diff(start: str, end: str) -> dict:
    """Difference between two ISO dates: total days/weeks and a calendar breakdown (years, months, days)."""
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    sign = -1 if b < a else 1
    first, last = (b, a) if sign < 0 else (a, b)
    months = (last.year - first.year) * 12 + last.month - first.month
    if last.day < first.day:
        months -= 1
    days = (last - _add_months(first, months)).days
    return {
        "total_days": (b - a).days,
        "total_weeks": round((b - a).days / 7, 2),
        "calendar": {"sign": sign, "years": months // 12, "months": months % 12, "days": days},
    }


@mcp.tool()
def weekday(date_iso: str) -> dict:
    """Weekday, ISO week number, day of year and leap-year flag for a date."""
    d = date.fromisoformat(date_iso)
    iso = d.isocalendar()
    return {
        "weekday": calendar.day_name[d.weekday()],
        "iso_week": iso.week,
        "iso_year": iso.year,
        "day_of_year": d.timetuple().tm_yday,
        "is_leap_year": calendar.isleap(d.year),
    }


@mcp.tool()
def period_bounds(date_iso: str, kind: PeriodKind) -> dict:
    """First and last day of the week (Mon-Sun), month, quarter or year containing the date."""
    d = date.fromisoformat(date_iso)
    match kind:
        case "week":
            start = d - timedelta(days=d.weekday())
            end = start + timedelta(days=6)
        case "month":
            start = d.replace(day=1)
            end = d.replace(day=calendar.monthrange(d.year, d.month)[1])
        case "quarter":
            first_month = 3 * ((d.month - 1) // 3) + 1
            start = date(d.year, first_month, 1)
            end = date(d.year, first_month + 2, calendar.monthrange(d.year, first_month + 2)[1])
        case "year":
            start, end = date(d.year, 1, 1), date(d.year, 12, 31)
    return {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1}


@mcp.tool()
def business_days(start: str, end: str, holidays: list[str] | None = None) -> int:
    """Count Mon-Fri days between two ISO dates, inclusive, excluding the optional ISO `holidays`."""
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    skipped = {date.fromisoformat(h) for h in holidays or []}
    return sum(1 for i in range((b - a).days + 1) if (d := a + timedelta(days=i)).weekday() < 5 and d not in skipped)


@mcp.tool()
def add_business_days(date_iso: str, amount: int, holidays: list[str] | None = None) -> str:
    """Move a date forward (or backward, if negative) by N business days, skipping weekends and `holidays`."""
    d = date.fromisoformat(date_iso)
    skipped = {date.fromisoformat(h) for h in holidays or []}
    step = 1 if amount >= 0 else -1
    remaining = abs(amount)
    while remaining:
        d += timedelta(days=step)
        if d.weekday() < 5 and d not in skipped:
            remaining -= 1
    return d.isoformat()


def create_app():
    """ASGI app serving MCP over streamable HTTP at /mcp, protected by a Keycloak bearer token."""
    app = mcp.streamable_http_app(host="0.0.0.0")
    settings = AuthSettings()
    if settings.auth_enabled:
        app.add_middleware(BearerAuthMiddleware, settings=settings)
    return app
