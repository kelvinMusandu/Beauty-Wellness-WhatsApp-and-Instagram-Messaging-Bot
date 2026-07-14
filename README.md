# WhatsApp Booking Bot for Beauty & Wellness Businesses

A WhatsApp-native booking system for Kenyan beauty & wellness businesses -
salons, spas, barbershops, nail studios, and similar service providers.
Customers book appointments and pay via M-Pesa entirely within WhatsApp -
no app download required.

Built in public. Follow the build log below.

## Status: Day 10 - Foundation + State Machine + Real Service & Provider Selection

- [x] Django project scaffolded
- [x] `webhooks` app receives GET (Meta verification) and POST (event storage)
- [x] Raw payloads stored immutably before any processing
- [x] Verified live against Meta's real servers (ngrok tunnel + WABA subscription)
- [x] Duplicate webhook deliveries detected and skipped (unique `message_id` + idempotency check)
- [x] First automated reply sent via Meta's Graph API, confirmed arriving on a real phone
- [x] Database schema: `Business`, `Service`, `Provider`, `Customer`, `Booking`
- [x] State machine: `IDLE → CHOOSING_SERVICE → CHOOSING_PROVIDER → CHOOSING_TIME → AWAITING_PAYMENT → CONFIRMED`, plus `HUMAN_TAKEOVER` from any state, session stored in Redis (Memurai locally)
- [x] `ConversationEvent` audit log (both directions) and `resume_bot` management command to restore a customer from `HUMAN_TAKEOVER`
- [x] `IDLE` and `CHOOSING_SERVICE` driven by real `Business`/`Service` data, not placeholder text - first real input validation (reject invalid replies, re-ask, instead of unconditionally advancing)
- [x] `CHOOSING_PROVIDER` driven by real `Provider` data, same validation pattern reused unchanged from service selection
- [ ] Real time slot selection with interval overlap detection (Day 11-12)
- [ ] Booking flow (Week 2)
- [ ] M-Pesa integration (Week 3)
- [ ] Admin dashboard (Week 3)
- [ ] Deploy + CI/CD (Week 4)

## Stack

Django · WhatsApp Cloud API · Redis (Memurai locally) · PostgreSQL (from deploy) ·
Next.js/TypeScript admin (Week 3) · Docker + GitHub Actions (Week 4)

## Engineering Principles

This project follows the rules in [best-practises.md](best-practises.md):
small verifiable steps, raw data stored before processing, idempotent
background jobs, infrastructure kept separate from business logic.

## Running Locally

```bash
python -m venv venv
./venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env           # then fill in WHATSAPP_VERIFY_TOKEN
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The webhook endpoint is `POST/GET /webhooks/whatsapp/`.

To let Meta reach your local server during development, expose it with a
tunnel (e.g. `ngrok http 8000`) and register the resulting HTTPS URL +
your `WHATSAPP_VERIFY_TOKEN` in the Meta developer dashboard.

## Build Log

- **Day 1:** Webhook endpoint verified by Meta. Incoming events stored raw
  in `WebhookEvent`, no processing yet - proves the wire is connected before
  building on top of it. Full setup + debugging notes:
  [week1/day1-meta-developer-setup-guide.md](../week1/day1-meta-developer-setup-guide.md).
- **Day 2:** WhatsApp can redeliver the same webhook on retry or timeout.
  Added a unique `message_id` field and a seen-before check before storing a
  new event, so the same message never creates two rows. Verified by sending
  an identical payload three times and confirming exactly one database row.
  DSA notes: [week1/day2-build-notes-dedup-dsa.md](../week1/day2-build-notes-dedup-dsa.md).
- **Day 3:** First outbound message. `send_whatsapp_message()` calls Meta's
  Graph API directly from the webhook view (synchronous, a known
  simplification until Celery/Redis exist). Genuine new messages get an
  automatic "Hello" reply; status updates and duplicates correctly stay
  silent. Also discovered status-update payloads carry their own id under
  `statuses[0].id`, not `messages[0].id` - `extract_message_id()` doesn't
  check that path yet, a real gap to close later. Verified with a real
  message, not just a 200: confirmed the reply physically arrived on a phone.
- **Day 4-5:** Database schema. New `bookings` app, separate from `webhooks`
  (Meta's HTTP interface vs core domain models). Five models: `Business`,
  `Service`, `Provider`, `Customer`, `Booking`. Booking's foreign keys use
  `PROTECT`, not `CASCADE` - deleting a business, customer, service, or
  provider should never silently delete booking history. `price_paid` is
  captured at booking time, not read from `Service.price` later, so old
  bookings show what was actually charged even if prices change afterward.
  No separate `TimeSlot` table - available slots get computed dynamically in
  Week 2, not stored. Verified with real linked data: created one of each
  model, confirmed relationships work, and specifically forced a `PROTECT`
  violation to prove deletion is actually blocked, not just assumed.
- **Day 6-7:** The state machine, and Redis for the first time (Memurai
  locally, a native Windows Redis-compatible server - Docker Desktop's
  Windows version requirement exceeded what this machine could support
  without a full OS upgrade). Seven states including `HUMAN_TAKEOVER`,
  triggered by "human," "agent," or "help" from any state, at which point
  the bot goes genuinely silent for that customer. Content per state is
  intentionally minimal, real service/provider/time lists are Week 2's job;
  today built the mechanism only. Verified twice: an isolated test cycling
  through all seven states in the shell, then a full real-world test
  sending actual WhatsApp messages through every transition, confirmed
  against the live Redis session state directly. Also added `ConversationEvent`,
  a human-readable log of both directions of every conversation (the customer's
  messages were already stored via `WebhookEvent`, but the bot's own replies
  weren't recorded anywhere until now), and `resume_bot`, a management command
  that restores a customer from `HUMAN_TAKEOVER` back to wherever they actually
  were - not a blanket reset to `IDLE` - using a single saved `previous_state`,
  not a full undo history. Verified with a real takeover: sent "human" mid-flow,
  confirmed the bot stayed silent through three follow-up messages including the
  literal word "resume," then ran the management command and confirmed the
  session was restored to the exact prior state. DSA notes:
  [week1/day6-7-build-notes-statemachine-dsa.md](../week1/day6-7-build-notes-statemachine-dsa.md).
- **Day 8-9:** `IDLE` and `CHOOSING_SERVICE` replaced with real logic - the
  state machine's first branches driven by actual data instead of placeholder
  text. New `bookings/booking_flow.py`: looks up which `Business` a
  conversation belongs to via Meta's stable `phone_number_id` (not the
  human-readable display number), fetches that business's active services
  ordered by `id` for a stable display order, and formats them into a numbered
  WhatsApp message. Also added `validate_number_choice()` - the project's
  first real input validation. Every state before this one advanced
  unconditionally regardless of what the customer typed; an invalid reply here
  (empty, non-numeric, or out of range) is rejected and the customer stays in
  `CHOOSING_SERVICE` until they answer correctly, done simply by not calling
  `set_state()` on a bad reply. Verified against a real WhatsApp number tied to
  a real `Business` row with three real services, not just a shell test. DSA
  notes: [week1/day8-9-build-notes-service-selection-dsa.md](../week1/day8-9-build-notes-service-selection-dsa.md).
- **Day 10:** `CHOOSING_PROVIDER` replaced with real logic - `get_active_providers()`
  and `format_provider_list()` in `bookings/booking_flow.py`, structurally identical
  to Day 8-9's service-selection functions, reused unchanged rather than redesigned.
  `CHOOSING_SERVICE`'s valid-choice branch also changed: it now checks that the
  business has active providers *before* committing the customer's service choice,
  so a business with services but no providers never leaves a customer stuck
  mid-flow holding a saved choice with nowhere to go next. Two real gaps found by
  testing on an actual phone, logged but deliberately not fixed yet: the numbered
  list doesn't re-appear on an invalid reply, and there's no self-service way for a
  customer to restart mid-flow (only paths back to `IDLE` are finishing the booking,
  an admin clearing the Redis session, or the 30-minute TTL expiring). Verified
  against a real WhatsApp number: invalid and out-of-range replies both correctly
  rejected and re-asked, valid service and provider choices both accepted and
  correctly stored. DSA notes:
  [week1/day10-build-notes-provider-selection-dsa.md](../week1/day10-build-notes-provider-selection-dsa.md).
