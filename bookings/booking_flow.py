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
