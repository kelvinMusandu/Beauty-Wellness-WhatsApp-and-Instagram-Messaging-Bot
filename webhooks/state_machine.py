import logging

import redis
from django.conf import settings

from bookings.booking_flow import (
    format_provider_list,
    format_service_list,
    get_active_providers,
    get_active_services,
    get_business_by_phone_number_id,
    validate_number_choice,
)
from bookings.models import Business

logger = logging.getLogger(__name__)

_redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

SESSION_TTL_SECONDS = 1800  # 30 minutes of inactivity resets a customer to IDLE

# Keywords that pull a customer out of the automated flow at any point,
# regardless of their current state. Checked before anything else.
HUMAN_TAKEOVER_KEYWORDS = {"human", "agent", "help"}


class State:
    """
    Conversation states. Not a Django model field, this never gets stored in
    the database, only in Redis, keyed by phone number.

    Content for CHOOSING_SERVICE / CHOOSING_PROVIDER / CHOOSING_TIME stays
    minimal today - real numbered lists driven by actual Service/Provider
    data are Week 2's job, not Day 6-7's. Today builds the mechanism.
    """

    IDLE = "IDLE"
    CHOOSING_SERVICE = "CHOOSING_SERVICE"
    CHOOSING_PROVIDER = "CHOOSING_PROVIDER"
    CHOOSING_TIME = "CHOOSING_TIME"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"


def _session_key(phone):
    return f"session:{phone}"


def get_state(phone):
    """
    Read a phone number's current state from Redis. Defaults to IDLE for a
    phone number with no session yet, or one that expired after 30 minutes
    of inactivity.
    """
    state = _redis_client.hget(_session_key(phone), "state")
    return state or State.IDLE


def set_state(phone, state):
    """
    Write a phone number's new state, refreshing the 30-minute TTL on every
    write, so an active conversation never expires mid-flow, only a
    genuinely abandoned one does.
    """
    key = _session_key(phone)
    _redis_client.hset(key, "state", state)
    _redis_client.expire(key, SESSION_TTL_SECONDS)


def resume_bot(phone):
    """
    Move a customer out of HUMAN_TAKEOVER, back into the automated flow.

    Resumes to wherever they actually were before requesting a human, not a
    blanket reset to IDLE - a customer one step from confirming a booking
    shouldn't have to start over just because they needed a quick
    clarification. Falls back to IDLE only if no prior state was saved
    (e.g., the session expired in the meantime).

    No dashboard exists yet (Week 3) - this is called from the
    resume_bot management command for now, the honest minimal way an
    admin can actually trigger this today.
    """
    key = _session_key(phone)
    previous_state = _redis_client.hget(key, "previous_state")
    restored_state = previous_state or State.IDLE

    set_state(phone, restored_state)
    _redis_client.hdel(key, "previous_state")

    logger.info("Resumed bot for %s, restored to state %s", phone, restored_state)
    return restored_state


def handle_message(phone, text, business_phone_number_id=None):
    """
    The actual state machine. Reads current state, decides the reply and
    next state, writes the new state back.

    business_phone_number_id identifies which Business this conversation
    belongs to (Meta's stable ID, not the display number) - needed from
    IDLE onward now that real service data drives the flow. Optional with
    a None default so existing calls (and tests) that don't care about
    business-specific content still work without every call site changing.

    Returns (reply_text, should_reply). should_reply is False specifically
    for HUMAN_TAKEOVER - the bot goes genuinely silent for that customer,
    not just quiet, matching the roadmap's Phase 2 human handoff design.
    """
    current_state = get_state(phone)

    if text and text.strip().lower() in HUMAN_TAKEOVER_KEYWORDS:
        # Save where they actually were, so resume_bot() can send them back
        # here instead of forcing a restart. Only save it the first time -
        # if they're already in HUMAN_TAKEOVER and say "human" again, don't
        # overwrite the real previous_state with HUMAN_TAKEOVER itself.
        if current_state != State.HUMAN_TAKEOVER:
            _redis_client.hset(_session_key(phone), "previous_state", current_state)
        set_state(phone, State.HUMAN_TAKEOVER)
        logger.info("Customer %s requested human takeover from state %s", phone, current_state)
        return "Connecting you with a team member, they'll be with you shortly.", True

    if current_state == State.HUMAN_TAKEOVER:
        # Bot stays silent. An admin resumes this from the dashboard later
        # (Week 3) - for now, silence is the entire mechanism.
        logger.info("Customer %s is in HUMAN_TAKEOVER, bot staying silent", phone)
        return None, False

    if current_state == State.IDLE:
        business = get_business_by_phone_number_id(business_phone_number_id)
        if business is None:
            logger.warning("No Business registered for phone_number_id=%s", business_phone_number_id)
            return "Sorry, this number isn't set up yet. Please try again later.", True

        services = get_active_services(business)
        if not services:
            return "Sorry, no services are available right now.", True

        _redis_client.hset(_session_key(phone), "business_id", business.id)
        set_state(phone, State.CHOOSING_SERVICE)
        return format_service_list(services), True

    if current_state == State.CHOOSING_SERVICE:
        business_id = _redis_client.hget(_session_key(phone), "business_id")
        if business_id:
            business = Business.objects.get(id=business_id)
        else:
            # Defensive fallback - should be unreachable, IDLE always sets
            # business_id before moving here. Re-derive from the WhatsApp
            # number if the session was somehow corrupted, same spirit as
            # the unreachable-state fallback at the bottom of this function.
            business = get_business_by_phone_number_id(business_phone_number_id)

        services = get_active_services(business)
        choice = validate_number_choice(text, len(services))

        if choice is None:
            # Stay in CHOOSING_SERVICE - no set_state() call. This is the
            # first real instance of "reject and re-ask" instead of
            # unconditionally advancing on any input.
            return f"Please reply with a number from 1 to {len(services)}.", True

        chosen_service = services[choice - 1]

        providers = get_active_providers(business)
        if not providers:
            # Don't commit service_id or advance state - the customer stays
            # in CHOOSING_SERVICE and can try again later, same as IDLE
            # bailing out before writing business_id if there are no services.
            return f"Got it, {chosen_service.name}. Sorry, no providers are available right now. Please try again later.", True

        _redis_client.hset(_session_key(phone), "service_id", chosen_service.id)
        set_state(phone, State.CHOOSING_PROVIDER)
        return format_provider_list(providers), True

    if current_state == State.CHOOSING_PROVIDER:
        business_id = _redis_client.hget(_session_key(phone), "business_id")
        if business_id:
            business = Business.objects.get(id=business_id)
        else:
            # Same unreachable-in-practice fallback as CHOOSING_SERVICE.
            business = get_business_by_phone_number_id(business_phone_number_id)

        providers = get_active_providers(business)
        choice = validate_number_choice(text, len(providers))

        if choice is None:
            # Stay in CHOOSING_PROVIDER - same reject-and-reask mechanism as
            # CHOOSING_SERVICE, no set_state() call on an invalid reply.
            return f"Please reply with a number from 1 to {len(providers)}.", True

        chosen_provider = providers[choice - 1]
        _redis_client.hset(_session_key(phone), "provider_id", chosen_provider.id)
        set_state(phone, State.CHOOSING_TIME)
        return f"Got it, {chosen_provider.name}. Now let's pick a time. (Real available slots: Day 11-12)", True

    if current_state == State.CHOOSING_TIME:
        set_state(phone, State.AWAITING_PAYMENT)
        return "Almost done. Payment integration comes in Week 3.", True

    if current_state == State.AWAITING_PAYMENT:
        set_state(phone, State.CONFIRMED)
        return "Your booking is confirmed! (Real M-Pesa flow: Week 3)", True

    if current_state == State.CONFIRMED:
        set_state(phone, State.IDLE)
        return "Starting a new booking. Reply with a number to choose a service.", True

    # Defensive fallback - should be unreachable given the states above
    # cover every defined State value, but never leave a customer stuck
    # with no reply if an unexpected state value somehow gets in.
    logger.warning("Unrecognised state %s for %s, resetting to IDLE", current_state, phone)
    set_state(phone, State.IDLE)
    return "Something went wrong, let's start over. Reply with a number to choose a service.", True


"""
My Notes

A state machine is a system that can be in exactly one state at a time, with defined rules for how 
it moves between states based on input. Three parts:

States - every possible situation the system can be in
A current state - where it is right now
Transition rules - given the current state and an input, move to a specific next state

Real-world example everyone already knows: a traffic light. It's always in exactly one state 
(red, yellow or green), never two at once, and it moves between them in a fixed, predictable order 
based on a timer input. 
A vending machine is another -
IDLE → ITEM_SELECTED → PAYMENT_PENDING → DISPENSING 
and it can't skip straight from IDLE to DISPENSING without passing through the states in between.

def set_state(phone, state):
    key = _session_key(phone)
    _redis_client.hset(key, "state", state)
    _redis_client.expire(key, SESSION_TTL_SECONDS)

Two separate Redis calls: hset writes the new state, expire resets the TTL countdown. The TTL gets 
refreshed on every write, not just once when the session is created - this is what makes an active 
conversation immune to expiring mid-flow (each message pushes the 30-minute clock back out) while a 
customer who genuinely walks away still resets to IDLE after half an hour of silence.

if current_state == State.IDLE:
    business = get_business_by_phone_number_id(business_phone_number_id)

First thing that happens once a phone number lands in IDLE: figure out which business this 
conversation belongs to, using the phone_number_id Meta attached to the webhook payload 
(extracted upstream by extract_business_phone_number_id() in views.py).


    if business is None:
        logger.warning(...)
        return "Sorry, this number isn't set up yet. Please try again later.", True

If no Business row matches that ID, the flow stops here with an honest error instead of crashing 
further down when something tries to use business.id. This is best-practises.md #3 in action - 
treat the external payload as untrusted, don't assume a match exists.


    services = get_active_services(business)
    if not services:
        return "Sorry, no services are available right now.", True

Same defensive pattern, one layer deeper: the business exists, but maybe it has zero active services 
configured. Rather than showing an empty numbered list ("Choose a service:\n" with nothing under it), 
bail with a clear message.

_redis_client.hset(_session_key(phone), "business_id", business.id)
    set_state(phone, State.CHOOSING_SERVICE)
    return format_service_list(services), True

Once both checks pass: remember which business this customer is talking to 
(written into the same Redis hash as state, under the session:{phone} key - 
this is the business_id field that CHOOSING_SERVICE reads back a moment later), 
advance the state machine one edge forward (IDLE → CHOOSING_SERVICE), and reply 
with the formatted list you just had explained. The , True is the should_reply half of the 
tuple - the bot always replies here, only HUMAN_TAKEOVER returns False.

business_id = _redis_client.hget(_session_key(phone), "business_id")
    if business_id:
        business = Business.objects.get(id=business_id)
    else:
        business = get_business_by_phone_number_id(business_phone_number_id)

This is the other half of the hset from IDLE - pulling business_id back out of Redis so 
the same business context survives across the two separate handle_message() calls (one per 
incoming WhatsApp message; nothing is held in memory between them, Redis is the only thing that 
persists). The else branch is a fallback that, per the comment, should never actually trigger - 
IDLE always sets business_id before a customer can reach CHOOSING_SERVICE at all. It exists purely 
as a second line of defense in case the Redis key somehow got corrupted or expired mid-flow, same 
philosophy as the exhaustiveness fallback at the very bottom of the function (documented in
Day 6-7 notes).

services = get_active_services(business)
    choice = validate_number_choice(text, len(services))

    if choice is None:
        return f"Please reply with a number from 1 to {len(services)}.", True

Re-fetches the same service list (needed again to validate the number and to look up the chosen one), 
then hands the customer's raw text to validate_number_choice(). If it comes back None - empty text, 
non-numeric, or out of range - the function returns here without calling set_state(). That's the whole 
mechanism for "stay in this state": simply never write a new state to Redis, so the next message that 
arrives still reads CHOOSING_SERVICE from get_state() and lands in this exact branch again. No special 
"reject" state was needed - just the absence of a transition.

    chosen_service = services[choice - 1]
    _redis_client.hset(_session_key(phone), "service_id", chosen_service.id)
    set_state(phone, State.CHOOSING_PROVIDER)
    return f"Got it, {chosen_service.name}. Now choose your provider. (Real provider list: Day 10)", True

Valid choice: convert the customer's 1-indexed display number back to a 0-indexed Python list position 
(choice - 1 - 
this is exactly why format_service_list() numbered starting at 1, so this line and that 
one agree on what "1" means), store which service was picked (same pattern as business_id) and 
advance one more edge (CHOOSING_SERVICE → CHOOSING_PROVIDER). The placeholder text in the reply is 
an honest admission that CHOOSING_PROVIDER itself isn't built yet - 
that's tomorrow's (Day 10) work, 
not hidden or faked today.

The throughline across both blocks: every piece of session data that needs to survive between one 
WhatsApp message and the next (business_id, service_id, state, previous_state) lives as a field in 
the same one Redis hash, following the exact grouping rationale your Day 6-7 notes already covered - 
one key, one expire(), no risk of the pieces drifting out of sync.
    
"""