# WhatsApp Bot Engineering Guide

### Lessons carried over from the football analytics project

This guide is intentionally about **engineering discipline**, not WhatsApp-specific APIs. The goal is to build a system that stays maintainable after months of iteration instead of becoming difficult to reason about.

---

# 1. Build in Small, Verifiable Steps

Never build an entire feature because it sounds useful.

Instead:

1. State the problem.
2. Define the smallest useful version.
3. Verify it works.
4. Expand only after proving value.

Good progression:

```
Webhook receives message
        ↓
Stores message
        ↓
Sends static reply
        ↓
Uses conversation history
        ↓
Calls an AI model
        ↓
Adds business logic
```

Avoid:

```
Webhook
+
AI
+
Memory
+
Scheduling
+
Analytics
+
Payments
+
CRM
+
Dashboard

...all in one pull request.
```

---

# 2. Verify Before You Build

One of the biggest lessons from this project:

> Never assume an external system contains a field or behaves the way documentation implies.

Always verify using real data.

Examples:

- Verify webhook payloads.
- Verify media payloads.
- Verify status callbacks.
- Verify template messages.
- Verify retry behaviour.
- Verify rate limits.

Don't write parsers from documentation alone.

Capture a real payload first.

---

# 3. Treat External Systems as Untrusted

Everything outside your application can change.

Examples:

- WhatsApp API
- Meta Cloud API
- Twilio
- Payment providers
- CRMs
- AI providers

Always assume:

- fields disappear
- fields become optional
- new event types appear
- retries happen
- duplicated webhooks happen

Write defensive code.

---

# 4. Store Raw Data First

Always save the original webhook before processing it.

Example flow:

```
Webhook

↓

Store raw payload

↓

Validate

↓

Process

↓

Business logic

↓

Reply
```

Raw payloads are invaluable for:

- debugging
- replaying events
- regression testing
- adapting to API changes

Never throw away the original request.

---

# 5. Separate Facts From Decisions

Store facts.

Compute decisions.

Example:

Facts

```
message
sender
timestamp
message_type
text
```

Decision

```
Should we reply?
```

The decision should never overwrite the original facts.

---

# 6. Make Every Background Job Idempotent

Redis workers will retry.

Railway may restart.

Messages may be delivered twice.

Jobs must be safe to execute multiple times.

Instead of:

```
Send message
```

Prefer:

```
If not already sent:

    Send

Mark sent
```

---

# 7. Never Mix Infrastructure With Business Logic

Bad:

```
Webhook

↓

Redis

↓

Database

↓

AI

↓

Business rules

↓

Formatting

↓

Response
```

inside one function.

Instead:

```
views.py

↓

services/

↓

repositories/

↓

workers/

↓

integrations/
```

Each layer has one responsibility.

---

# 8. Every New Feature Starts as a Roadmap

Before writing code, document:

## Problem

What is actually missing?

## Hypothesis

Why will this improve the product?

## Scope

What exactly will be built?

## Non-goals

What explicitly will NOT be built?

## Verification plan

How will we know it works?

This prevents scope creep.

---

# 9. Features Must Earn Their Way In

Don't add something because it seems clever.

Add it because it answers a real user question.

Ask:

> What question does this feature answer?

If you cannot answer that clearly,

don't build it.

---

# 10. Keep Raw Data Immutable

Never overwrite incoming events.

Instead:

```
messages

conversation_events

jobs

responses
```

should all be append-only where practical.

Derived state belongs elsewhere.

---

# 11. Redis Is a Queue, Not Your Database

Redis is excellent for:

- queues
- caching
- locks
- rate limiting
- temporary state

Redis is not your source of truth.

Persistent data belongs in PostgreSQL.

If Redis disappears,

your application should recover.

---

# 12. Railway Is Disposable

Assume every deployment can restart at any moment.

Never rely on:

- in-memory state
- global variables
- Python caches

Everything important belongs in:

- PostgreSQL
- Redis
- object storage

---

# 13. Log Decisions, Not Just Errors

Good logs explain why something happened.

Instead of:

```
Message processed
```

Prefer:

```
Ignoring duplicate webhook

Customer already replied

Conversation locked

AI skipped because confidence below threshold

Template rejected because variables missing
```

Future debugging becomes dramatically easier.

---

# 14. Make Every AI Decision Explainable

If AI chooses an action,

store why.

Example:

```
Intent:
Support

Confidence:
0.91

Reason:
Customer asked about refund status.
```

Never make AI a black box.

---

# 15. Prefer Configuration Over Code

Things likely to change belong in configuration.

Examples:

- prompts
- business hours
- rate limits
- allowed phone numbers
- feature flags

Avoid hardcoding values throughout the project.

---

# 16. Test With Real Payloads

Synthetic payloads are useful.

Real payloads are essential.

Keep anonymized examples for:

- text
- images
- documents
- locations
- reactions
- interactive buttons
- template replies

Regression testing becomes much easier.

---

# 17. Document Every Architectural Decision

Keep lightweight roadmap documents for ideas before implementation.

Each document should record:

- why the idea came up
- alternatives considered
- trade-offs
- reasons for acceptance or rejection
- requirements before implementation

Future contributors should understand why something exists—not just how it works.

---

# 18. Optimize Only After Measurement

Do not introduce caching, batching, sharding, or complex concurrency because they "might be needed."

Measure first.

Then optimize the bottleneck that actually exists.

---

# 19. Build for Recovery

Every important operation should answer:

- Can it be retried?
- Can it be replayed?
- Can it be resumed?
- Can it fail safely?

Recovery is more valuable than preventing every failure.

---

# 20. Keep the Architecture Honest

Every component should have a clear purpose.

Django

- HTTP API
- Admin
- Models
- Authentication

Redis

- Queue
- Cache
- Locks

Workers

- Long-running tasks
- AI calls
- Media processing
- Scheduled jobs

PostgreSQL

- Source of truth

Railway

- Hosting only

Avoid letting any technology take on responsibilities it wasn't chosen for.

---

# Core Engineering Philosophy

The most important lesson from this project is simple:

> Build only what solves a demonstrated problem. Verify every external assumption with real data before writing ingestion code. Preserve raw facts, derive insights separately, and keep every new capability small enough to prove its value before expanding it.

A WhatsApp bot built this way remains understandable, testable, and resilient as it grows. The goal is not to build the most feature-rich bot as quickly as possible, but to build one whose behaviour, data flow, and architectural decisions remain clear months or years later.
