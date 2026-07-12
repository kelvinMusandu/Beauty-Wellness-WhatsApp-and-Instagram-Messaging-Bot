import logging

import redis
from django.conf import settings

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


def handle_message(phone, text):
    """
    The actual state machine. Reads current state, decides the reply and
    next state, writes the new state back.

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
        set_state(phone, State.CHOOSING_SERVICE)
        return "Welcome! Reply with a number to choose a service. (Real service list: Week 2)", True

    if current_state == State.CHOOSING_SERVICE:
        set_state(phone, State.CHOOSING_PROVIDER)
        return "Got it. Now choose your provider. (Real provider list: Week 2)", True

    if current_state == State.CHOOSING_PROVIDER:
        set_state(phone, State.CHOOSING_TIME)
        return "Now let's pick a time. (Real available slots: Week 2)", True

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


"""