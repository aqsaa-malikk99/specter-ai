"""Deadline Agent.

Deliberately deterministic, not an LLM call: once the Clause Extraction Agent has
converted the notice-window language into structured values (notice_window_days,
term_length_months), the actual cancel-by date is arithmetic. Doing that arithmetic
in code instead of asking the model to compute it removes an entire class of
off-by-one-day / bad-math failures.
"""
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from ics import Calendar, Event

from app.agents.schemas import AutoRenewalClause, DeadlineResult

REMINDER_OFFSETS_DAYS = (90, 30, 7)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def compute_deadline(
    effective_date: str | None,
    term_length_months: int | None,
    auto_renewal: AutoRenewalClause,
) -> DeadlineResult:
    if not auto_renewal.present or not auto_renewal.notice_window_days:
        return DeadlineResult(
            cancel_by_date=None,
            reminder_dates=[],
            reasoning="No auto-renewal clause detected, or notice window could not be determined.",
        )

    eff = _parse_date(effective_date)
    if not eff or not term_length_months:
        return DeadlineResult(
            cancel_by_date=None,
            reminder_dates=[],
            reasoning="Auto-renewal clause found but effective_date or term_length_months is missing, "
            "so the renewal date cannot be computed.",
        )

    renewal_date = eff + relativedelta(months=term_length_months)
    cancel_by = renewal_date - timedelta(days=auto_renewal.notice_window_days)
    reminders = [cancel_by - timedelta(days=d) for d in REMINDER_OFFSETS_DAYS]

    return DeadlineResult(
        cancel_by_date=cancel_by.isoformat(),
        reminder_dates=[r.isoformat() for r in reminders],
        reasoning=(
            f"Renewal date = effective_date ({eff.isoformat()}) + {term_length_months} months "
            f"= {renewal_date.isoformat()}. Cancel-by = renewal date - "
            f"{auto_renewal.notice_window_days} day notice window = {cancel_by.isoformat()}."
        ),
    )


def build_ics(contract_type: str, deadline: DeadlineResult) -> str:
    cal = Calendar()
    if deadline.cancel_by_date:
        event = Event()
        event.name = f"Cancel-by deadline: {contract_type}"
        event.begin = deadline.cancel_by_date
        event.make_all_day()
        event.description = deadline.reasoning
        cal.events.add(event)
    for reminder in deadline.reminder_dates:
        ev = Event()
        ev.name = f"Renewal reminder: {contract_type}"
        ev.begin = reminder
        ev.make_all_day()
        cal.events.add(ev)
    return str(cal.serialize())
