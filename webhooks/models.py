from django.db import models # pulls in Django's ORM (Object-Relational Mapper) module


class WebhookEvent(models.Model):

    raw_payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    # WhatsApp's own unique ID for a message (e.g. "wamid.HBgM..."). Not every
    # webhook has one (status updates, some payload shapes don't include it) so
    # this is nullable — but where it exists, it must be unique. This is the
    # hash-table "seen before" check: null=True lets many non-message events
    # have no id, unique=True means Django/Postgres reject a second row with
    # the same real message_id at the database level, not just in application code.
    message_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    # Set once a background worker has looked at this event (Day 3+).
    # Day 1 leaves this False for everything — no processing happens yet.
    processed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-received_at'] # orders the data model level is descending order

    def __str__(self):
        return f"WebhookEvent {self.id} @ {self.received_at:%Y-%m-%d %H:%M:%S}" #  it defines 
        # what string representation Python/Django uses when something needs to display this 
        # object as text (admin lists, print(), logs, f-strings, etc.).


"""
My Notes:
models.py definrs how a database table is going to look like 

this table's whole purpose is being an audit trail.

raw_payload — a JSONField storing the entire, untouched JSON body Meta sends on every webhook call.
received_at — auto-set timestamp of when it arrived.
processed — a boolean flag, currently unused (default=False for everything), reserved for 
a future background worker to mark once it's handled the event.

Raw storage of every incoming WhatsApp webhook payload.
best practises:
1. store raw data first, before any processing. This ensures that data integrity/originality is high from the start.
2. keep raw data immutable, append-only.

Nothing in this table is ever edited after creation. Parsing, state
machine transitions, and business logic all read FROM this table —
they never write back to it.

A class in Python is a blueprint for creating objects — it bundles together data (attributes) and
behavior (methods) into a single reusable definition.

Basic syntax:


class Dog:
    def __init__(self, name):
        self.name = name

    def bark(self):
        return f"{self.name} says woof!"

class Dog: defines the blueprint.
__init__ is the constructor — runs automatically when you create a new instance, setting up its initial data.
self refers to "this particular instance" — how a method accesses/modifies that instance's own data.
bark is a method — behavior every Dog instance can do.
Using it:


rex = Dog("Rex")   # creates an "instance" of the class
rex.bark()          # "Rex says woof!"

A function is a standalone, reusable block of code — it doesn't belong to any object:


def add(a, b):
    return a + b

add(3, 4)   # 7
A method is a function that's defined inside a class and operates on an instance of that class. 
It's called through an object, using dot notation, and it implicitly receives that object as its 
first argument (self):


class Dog:
    def bark(self):          # <- this is a method
        return f"{self.name} says woof!"

rex.bark()   # called on a specific instance

When plain functions are the right call:
Stateless logic — something that just transforms input to output with nothing to "remember"
 (e.g. format_phone_number(raw), parse_message_text(payload)).
One-off scripts, utility/helper code, data processing pipelines.
Most of actual business logic in a Django project (parsing a webhook payload, deciding 
how to reply) is often cleaner as plain functions in a utils.py or services.py, not shoehorned 
into a class.

When classes/methods actually earn their keep:
You have data + behavior that belong together and need to persist or be passed around as one unit 
this is exactly why WebhookEvent is a class: it's not just logic, it's a thing (a database row) 
with fields and behavior tied to that specific row.
Django itself requires classes in specific places by framework convention — models (models.Model), 
class-based views, forms, serializers, you inherit from Django's base classes to plug 
into its machinery (ORM, admin, etc.).
You need multiple independent instances of something with their own state (like each Dog having its 
own name, or each WebhookEvent being its own row with its own id/payload/timestamp).

"""
