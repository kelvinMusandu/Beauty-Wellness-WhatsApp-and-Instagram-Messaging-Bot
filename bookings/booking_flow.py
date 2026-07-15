from datetime import datetime, timedelta

from .models import Booking, Business, Provider, Service

SLOT_INTERVAL_MINUTES = 30


def get_business_by_phone_number_id(phone_number_id):
    """
    Look up which Business a conversation belongs to, using Meta's stable
    phone_number_id (not the display number). Returns None if no business
    is registered for that number yet - callers must handle this, not
    assume a match always exists.
    """
    try:
        return Business.objects.get(whatsapp_number=phone_number_id)
    except Business.DoesNotExist:
        return None


def get_active_services(business):
    """
    Ordered by id, not name or price - the display numbers shown to a
    customer (1, 2, 3...) must correspond to a stable, repeatable order,
    or the same customer could see service #2 change between messages if
    an unordered query happened to return rows differently.
    """
    return list(Service.objects.filter(business=business, is_active=True).order_by("id"))


def format_service_list(services):
    lines = [f"{i}. {s.name} - KES {s.price}" for i, s in enumerate(services, start=1)]
    return "Welcome! Choose a service:\n" + "\n".join(lines)


def get_active_providers(business):
    """
    Ordered by id, same rationale as get_active_services - the display
    numbers shown to a customer must stay stable and repeatable across
    messages, not just correct at the moment of a single query.
    """
    return list(Provider.objects.filter(business=business, is_active=True).order_by("id"))


def format_provider_list(providers):
    lines = [f"{i}. {p.name}" for i, p in enumerate(providers, start=1)]
    return "Now choose your provider:\n" + "\n".join(lines)


def get_available_slots(business, provider, service, on_date):
    """
    Generates candidate start times between the business's opening and
    closing time, spaced SLOT_INTERVAL_MINUTES apart, then filters out any
    that would overlap an existing booking for this provider on this date -
    interval overlap detection (week2/day1-interval-overlap.md). No
    TimeSlot table exists (a Day 4-5 decision) - slots are computed fresh on
    every request, not read back from stored rows.
    """
    duration = timedelta(minutes=service.duration_minutes)
    # timedelta is Python's representation of a span of time 
    # (as opposed to a specific point in time). service.duration_minutes is a 
    # plain integer field on the model (e.g. 60); wrapping it in 
    # timedelta(minutes=...) turns that integer into something you can 
    # actually add to or subtract from a datetime a few lines down.

    current = datetime.combine(on_date, business.opens_at)
    closing = datetime.combine(on_date, business.closes_at)
    # on_date is a date (just a calendar day, no time-of-day). 
    # business.opens_at/closes_at are TimeFields (just a time-of-day, 
    # no calendar day). Neither on its own is enough to do arithmetic with - 
    # you can't sensibly add "30 minutes" to a bare date, and a bare time has no 
    # sense of "the next day" if it rolls over. datetime.combine(date, time) 
    # glues the two into one full datetime - e.g. date(2026, 7, 15) + time(9, 0) 
    # → datetime(2026, 7, 15, 9, 0). Now both current and closing are full 
    # datetimes you can subtract, compare and add timedeltas to.

    slots = []
    while current + duration <= closing:
        start_time = current.time()
        end_time = (current + duration).time()
        if not _has_conflict(provider, on_date, start_time, end_time):
            slots.append(start_time)
        # For this specific candidate window, ask _has_conflict() 
        # (explained below) whether it overlaps an existing booking for 
        # this provider on this date. Only append it to slots if the answer 
        # is no - a rejected candidate is simply never added, not marked or flagged.

        current += timedelta(minutes=SLOT_INTERVAL_MINUTES)
        # Advances the loop by 30 minutes and goes back to the while check. 
        # current += timedelta(...) is shorthand for current = current + 
        # timedelta(...) - datetimes support +/+= with timedeltas directly, one 
        # of the reasons datetime.combine() was needed earlier rather than juggling 
        # separate date/time values through the whole loop.

    return slots


def _has_conflict(provider, on_date, start_time, end_time):
    """
    Interval overlap: existing.start < requested.end AND existing.end >
    requested.start. Cancelled bookings don't block a slot - only ones that
    could still become real do.
    """
    return (
        Booking.objects.filter(provider=provider, date=on_date)
        .exclude(status=Booking.Status.CANCELLED)
        .filter(start_time__lt=end_time, end_time__gt=start_time)
        .exists()
        # .filter(provider=provider, date=on_date) - only bookings for 
        # this specific stylist, on this specific day. Everything else is 
        # irrelevant to whether this candidate slot is free.

        # .exclude(status=Booking.Status.CANCELLED) - a cancelled booking doesn't 
        # actually occupy the calendar anymore, so it shouldn't block a slot. 
        # Everything else (pending, awaiting_payment, confirmed, completed) 
        # still counts as "occupying time."

        # .filter(start_time__lt=end_time, end_time__gt=start_time) - this is 
        # the actual interval overlap condition from your DSA notes: 
        # existing.start < requested.end AND existing.end > requested.start. 
        # Django ANDs multiple conditions in one .filter() call by default, 
        # so this single line expresses both halves of the formula. __lt and __gt 
        # are Django's field-lookup suffixes for "less than" and "greater than" - 
        # there's no </> operator usable directly on ORM fields, so Django uses 
        # these string suffixes instead.

        # .exists() — runs an efficient SELECT 1 ... LIMIT 1-style check against 
        # the database and returns a plain True/False, rather than fetching full 
        # rows just to check whether any exist.
    )


def format_slot_list(slots, on_date):
    lines = [f"{i}. {slot.strftime('%H:%M')}" for i, slot in enumerate(slots, start=1)]
    return f"Choose a time for {on_date.strftime('%A, %d %b')}:\n" + "\n".join(lines)


def validate_number_choice(text, max_value):
    """
    Returns the 1-indexed integer choice if text is a valid number within
    range, otherwise None. This is the actual validation that was missing
    since Day 6-7 - the first real instance of "reject invalid input and
    ask again" instead of unconditionally advancing.
    """
    if not text:
        return None

    stripped = text.strip()
    if not stripped.isdigit():
        return None

    choice = int(stripped)
    if choice < 1 or choice > max_value:
        return None

    return choice

"""
My Notes

def format_service_list(services):
Takes a list of Service objects (already fetched and ordered by get_active_services()) and 
turns it into the actual text message a customer sees.


lines = [f"{i}. {s.name} - KES {s.price}" for i, s in enumerate(services, start=1)]

This is a list comprehension - a compact way to build a new list by transforming each item in an 
existing one, all in a single expression instead of a multi-line loop. Let me unpack the two things 
happening inside it.

enumerate(services, start=1) - a Python built-in that pairs each item in a list with a number, so you 
get both the position and the item together as you iterate. Without start=1, numbering would begin at 
0 (Python's default), which would show customers "0. Haircut" instead of "1. Haircut" - a mismatch 
nobody wants. With three services, this produces:

(1, <Service: Haircut>)
(2, <Service: Manicure>)
(3, <Service: Braids>)

The comprehension itself - [expression for i, s in enumerate(...)] reads as: "for each (i, s) pair, 
produce f"{i}. {s.name} - KES {s.price}", and collect all of those into a new list." Written the 
long way, without a comprehension, this same line would be:


lines = []
for i, s in enumerate(services, start=1):
    lines.append(f"{i}. {s.name} - KES {s.price}")

Both produce the exact same result - the comprehension is just the same loop compressed into one line, 
a very common Python idiom once you're used to reading them.

What lines actually contains, given the real test data from today's live test:


[
    "1. Haircut - KES 500.00",
    "2. Manicure - KES 800.00",
    "3. Braids - KES 1500.00",
]

return "Welcome! Choose a service:\n" + "\n".join(lines)
"\n".join(lines) - takes the list of strings and glues them together into one single string, inserting 
"\n" (a newline character) between each item. This is the reverse operation of splitting a string 
apart - join() is a string method called on the separator, with the list passed as its argument 
(a detail worth noting since it reads slightly backwards from what people expect the first time: 
it's separator.join(list), not list.join(separator)).

Then "Welcome! Choose a service:\n" + ... - plain string concatenation, prepending a header line 
before the joined list, with its own trailing \n so the first service starts on a new line rather 
than right after the colon.

The actual final output, confirmed from your real test

Welcome! Choose a service:
1. Haircut - KES 500.00
2. Manicure - KES 800.00
3. Braids - KES 1500.00
Exactly what arrived on your phone during today's live test - every piece of this function traces 
directly to that real message.

"""
