# WhatsApp Booking Bot for Beauty & Wellness Businesses

A WhatsApp-native booking system for Kenyan beauty & wellness businesses -
salons, spas, barbershops, nail studios, and similar service providers.
Customers book appointments and pay via M-Pesa entirely within WhatsApp -
no app download required.

Built in public. Follow the build log below.

## Status: Day 4-5 - Foundation + Duplicate Handling + First Reply + Database Schema

- [x] Django project scaffolded
- [x] `webhooks` app receives GET (Meta verification) and POST (event storage)
- [x] Raw payloads stored immutably before any processing
- [x] Verified live against Meta's real servers (ngrok tunnel + WABA subscription)
- [x] Duplicate webhook deliveries detected and skipped (unique `message_id` + idempotency check)
- [x] First automated reply sent via Meta's Graph API, confirmed arriving on a real phone
- [x] Database schema: `Business`, `Service`, `Provider`, `Customer`, `Booking`
- [ ] State machine (Day 6–7)
- [ ] Booking flow (Week 2)
- [ ] M-Pesa integration (Week 3)
- [ ] Admin dashboard (Week 3)
- [ ] Deploy + CI/CD (Week 4)

## Stack

Django · WhatsApp Cloud API · Redis (from Week 1) · PostgreSQL (from deploy) ·
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
