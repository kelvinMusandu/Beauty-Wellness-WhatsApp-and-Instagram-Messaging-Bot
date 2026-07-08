# WhatsApp Salon Booking Bot

A WhatsApp-native booking system for Kenyan salons. Customers book appointments
and pay via M-Pesa entirely within WhatsApp — no app download required.

Built in public. Follow the build log below.

## Status: Day 1 — Foundation

- [x] Django project scaffolded
- [x] `webhooks` app receives GET (Meta verification) and POST (event storage)
- [x] Raw payloads stored immutably before any processing
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
  in `WebhookEvent`, no processing yet — proves the wire is connected before
  building on top of it.
