# Python standard library (json, logging), 
# Django framework pieces (settings, http, decorators),
# app's code (.models).

import json
import logging

import requests
from django.conf import settings
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import WebhookEvent

logger = logging.getLogger(__name__)


def extract_message_id(payload):
    """
    Defensively pull the message id out of a WhatsApp webhook payload.

    Not every payload has this shape — status updates, the dashboard's test
    payload, and future webhook types may not include a "messages" list at
    all. Uses .get() chains, not direct indexing, so an unexpected shape
    returns None instead of raising KeyError/IndexError.
    """
    try:
        entry = payload.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        messages = change.get("value", {}).get("messages", [])
        return messages[0].get("id") if messages else None
    except (IndexError, AttributeError, TypeError):
        return None


def extract_sender_phone(payload):
    """
    Defensively pull the sender's phone number out of a WhatsApp webhook
    payload. Same shape assumptions as extract_message_id — status updates
    and other non-message webhook types won't have this field either.
    """
    try:
        entry = payload.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        messages = change.get("value", {}).get("messages", [])
        return messages[0].get("from") if messages else None
    except (IndexError, AttributeError, TypeError):
        return None


def send_whatsapp_message(to, text):
    """
    Send a text message via Meta's Graph API.

    Day 3: synchronous, called directly inside the webhook view. This is a
    known simplification, not an oversight — best-practises.md #1 says build
    the smallest working version first. Moving this to a background task
    (Celery) happens once that infrastructure exists, Day 6-7 alongside the
    state machine, not before it's actually needed.
    """
    url = f"https://graph.facebook.com/v25.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    response = requests.post(url, headers=headers, json=body, timeout=10)

    if response.status_code == 200:
        logger.info("Sent WhatsApp reply to %s", to)
    else:
        logger.warning(
            "Failed to send WhatsApp reply to %s: status=%s body=%s",
            to, response.status_code, response.text,
        )

    return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        return _verify(request) # undescore in a function indicates it is a private function, 
                                # meaning it should not be called from outside the file
    return _receive(request)


def _verify(request):
    """
    Meta's one-time webhook verification handshake.

    When you register this URL in the Meta developer dashboard, Meta sends
    a GET request with hub.mode, hub.verify_token, hub.challenge.
    If the token matches what you configured, echo back hub.challenge.
    """
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge", "")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verification succeeded")
        return HttpResponse(challenge, status=200)

    logger.warning("Webhook verification failed: mode=%s token_match=%s", mode, token == settings.WHATSAPP_VERIFY_TOKEN)
    return HttpResponseForbidden("Verification failed")


def _receive(request):
    """
    Store the raw webhook payload and respond immediately.

    Best Practises
    Store raw data first, before validating or processing.
    This endpoint does no real work. Meta expects
    a fast 200. Parsing and replying happen in a later step (Day 3+), not here.

    Duplicate handling (Day 2): WhatsApp can redeliver the same webhook on
    retry/timeout. message_id is the hash-table "seen before" check - if we
    already have a row with this message_id, skip creating a second one.
    Still respond 200 either way, so Meta doesn't keep retrying a message
    we've already handled.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("Received non-JSON body on webhook POST")
        return HttpResponse(status=400)

    message_id = extract_message_id(payload)

    if message_id and WebhookEvent.objects.filter(message_id=message_id).exists():
        logger.info("Duplicate webhook for message_id=%s, skipping", message_id)
        return HttpResponse(status=200)

    try:
        event = WebhookEvent.objects.create(raw_payload=payload, message_id=message_id)
        logger.info("Stored webhook event id=%s message_id=%s", event.id, message_id)

        # Day 3: reply to genuine new messages only. message_id and sender
        # are both None for status updates and other non-message webhook
        # types, so this naturally skips those without a separate check.
        sender = extract_sender_phone(payload)
        if message_id and sender:
            send_whatsapp_message(sender, "Hello")
    except IntegrityError:
        # Race condition: two requests with the same message_id passed the
        # .exists() check before either had committed. The unique constraint
        # on message_id catches what the pre-check couldn't.
        logger.info("Duplicate webhook for message_id=%s (race), skipping", message_id)

    return HttpResponse(status=200)


"""
My Notes:

This the entry point of the whole bot. It's the piece that turns "someone messaged your WhatsApp
number" into "a row in the database." Meta expects a quick 200 response on every webhook call, 
and if you're slow (e.g., you tried to parse the message, call an LLM, and send a reply all 
synchronously inside this view), Meta may retry or eventually disable your webhook.

What it does, function by function:

whatsapp_webhook (webhooks/views.py:16) the single URL Meta calls, routing by HTTP method: 
GET for verification, POST for actual incoming messages.

_verify (webhooks/views.py:22) handles Meta's one-time handshake when you first register 
the webhook URL in the developer dashboard. Meta sends hub.mode, hub.verify_token, hub.challenge 
as query params; if the token matches your WHATSAPP_VERIFY_TOKEN (from config/settings.py:33), you 
echo back the challenge to prove you control this endpoint. This is the practical use of that setting 
you asked about earlier.

_receive (webhooks/views.py:42) handles every actual incoming WhatsApp event. It parses 
the JSON body and immediately saves it via WebhookEvent.objects.create(raw_payload=payload) directly 
exercising the model you were just reading. No parsing of message content, no reply logic, nothing 
just capture and return 200.

Two decorators worth explaining:

@csrf_exempt (webhooks/views.py:14) Django's CSRF protection assumes requests come from your 
own site's forms with a token. Meta's servers can't provide that token, so this view has to opt out 
of CSRF (Cross-Site Request Forgery) checking, or Meta's POSTs would be rejected outright.

@require_http_methods(["GET", "POST"]) hard-rejects any other HTTP method (PUT, DELETE, etc.) with 
a 405, reducing attack surface.

When Meta sends the verification GET request, the parameters are appended to your webhook URL as a 
query string, something like:

https://yourdomain.com/webhook/?hub.mode=subscribe&hub.verify_token=your_secret_token&hub.challenge=1234567890
Everything after the ? is the query string key=value pairs separated by &. Django automatically parses 
that into request.GET, a dict-like object, so:

request.GET.get("hub.mode")           # -> "subscribe"
request.GET.get("hub.verify_token")   # -> "your_secret_token"
request.GET.get("hub.challenge", "")  # -> "1234567890"

GET → data in the URL's query string → used for the one-time verification handshake. POST → data in the 
request body → used for every real webhook event afterward.

A race condition happens when two or more operations run concurrently (at the same time or interleaved) 
and the outcome depends on which one happens to finish first, timing that isn't guaranteed. 
It's a bug class specific to concurrent/parallel systems.

"Race condition: two 
requests with the same message_id passed the .exists() check before either had committed."

Meta retries on any non-200 or slow response meaning that two requests can be sent and
the check may run concurrently both could pass the check before either has written "processed"
and we'd handle the same message twice. 

How do we catch the race condition?
if ... WebhookEvent.objects.filter(message_id=message_id).exists(). 
This asks "have I already seen this message?" But this check and the eventual create() 
are two separate operations, not one atomic step.
The race window: if two webhook deliveries for the same message arrive close together, both requests 
can run the if statement, both see "no existing row" (because neither has committed yet), and both proceed to 
try creating a row.

both attempt WebhookEvent.objects.create(...). The database itself has a unique constraint on 
message_id (visible from the comment at line 97-99), so whichever request's INSERT lands second gets rejected 
by the database with an IntegrityError — not because logic caught it, but because the database 
enforces uniqueness at the storage layer, which is atomic in a way our .filter().exists() 
check in the logic isn't.

Idempotency is performing the same operation multiple times and have the same effect as performing it once. 
Calling it once or calling it ten times with identical input leaves the system in the same end state.

The message_id uniqueness check (webhooks/views.py:87-91) — before inserting, check if a row with this 
message_id already exists; if so, skip and return 200 anyway.
The database-level unique constraint + IntegrityError catch (webhooks/views.py:93-100) — the race-condition 
backstop we just discussed, guaranteeing correctness even if two near-simultaneous deliveries both slip past 
the first check.

Always returning 200, even on the duplicate path, this isthe other half of idempotency: telling Meta 
"I've got it, stop retrying" regardless of whether this particular delivery was new or a repeat. 
If we returned an error on duplicates, Meta would just keep retrying 
forever.

Atomicity means an operation is treated as a single, indivisible unit; it either completes entirely 
or it doesn't happen at all. There's no observable "halfway done" state that anything else can see or 
be affected by.

A single INSERT statement (like WebhookEvent.objects.create(...)) is atomic at the database level,
the database guarantees that checking the unique constraint on message_id and actually writing the row 
happen as one indivisible operation. 
No other request can sneak in "between" the constraint check and the write.

if we ever need multiple related writes to succeed or fail together 
(e.g., "create the event AND update a counter AND log an action" none of which should partially 
apply if one fails), we'd wrap them in django.db.transaction.atomic(), which extends this same 
guarantee across multiple statements, not just one. Our current code doesn't need this yet since it 
only performs a single create() call per request but it's the tool we'd reach for once _receive starts 
doing more than one write per request.

Big-O notation describes how an operation's cost (usually time, sometimes memory) 
grows as the size of the input grows, not exact seconds, but the shape of the growth curve as 
things scale.

O(1) — Constant Time
The operation takes the same number of steps no matter how large the collection is. 10 rows or 
10 million rows, same cost.

Example — hash table lookup:


d = {"a": 1, "b": 2, ...}  # even with a million keys
d["a"]  # still one hash computation, one jump to a slot

Whether the dict has 3 keys or 3 million, computing the hash of "a" and jumping to that slot takes the 
same number of operations. That's what "constant" means — flat, unaffected by n.

O(log n) — Logarithmic Time
The operation's cost grows, but very slowly, each additional step you take roughly cuts the remaining 
search space in half. This is what a B-tree index (like our message_id unique constraint) does,
"is it in the left half or the right half?" repeatedly, until you land on the answer.

WebhookEvent.objects.filter(message_id=message_id).exists()

This line asks the database: "search through the WebhookEvent table, does any existing row have this value?"

so in O(log n) n refers to the number of rows in the table but PostgreSQL uses B-Tree index built from
unique=True to answer withouts scanning every row one by one.

B-Tree is a self-balancing, multi-way search tree data structure designed to optimize storage system 
operations, particularly on secondary storage devices like hard drives and flash memory. 

this query is instant regardless of whether it's technically O(1) or O(log n)
the difference is invisible at this size. The distinction only starts to matter once the table has 
millions of rows: a true hash table would still answer in one step, while the B-tree index needs a small, 
slowly-growing number of comparisons. Neither is "slow" in practice — both are considered fast
but they're not identical, and that's the nuance from the previous file's hash-table-vs-B-tree table.
"""
