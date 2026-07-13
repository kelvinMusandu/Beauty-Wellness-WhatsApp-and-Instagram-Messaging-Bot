from .models import Business, Service


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
