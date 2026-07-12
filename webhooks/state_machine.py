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
