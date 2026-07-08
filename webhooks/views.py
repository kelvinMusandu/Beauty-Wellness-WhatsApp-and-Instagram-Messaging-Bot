# Python standard library (json, logging), 
# Django framework pieces (settings, http, decorators),
# app's code (.models).

import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import WebhookEvent

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        return _verify(request)
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
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("Received non-JSON body on webhook POST")
        return HttpResponse(status=400)

    event = WebhookEvent.objects.create(raw_payload=payload)
    logger.info("Stored webhook event id=%s", event.id)

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
"""
