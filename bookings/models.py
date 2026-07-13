from django.db import models


class Business(models.Model):
    """
    A beauty & wellness business, salon, spa, barbershop, nail studio, or
    similar. Generic naming deliberately, not "Salon", works identically
    for any appointment-based service business.
    """

    name = models.CharField(max_length=255)

    # Meta's stable phone_number_id (from webhook payload metadata), not the
    # human-readable display number. The ID is what identifies which
    # business a conversation belongs to when a message arrives - the same
    # value used to construct the Graph API send-message URL.
    whatsapp_number = models.CharField(max_length=20, unique=True)
    opens_at = models.TimeField(default="09:00")
    closes_at = models.TimeField(default="18:00")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Service(models.Model):
    """What a business offers - a haircut, a manicure, a massage."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(default=60)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class Provider(models.Model):
    """Who performs the service - a stylist, technician, or therapist."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="providers")
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class Customer(models.Model):
    """
    The person booking. phone is the same value that arrives as "from" in
    WhatsApp webhook payloads - the link between a real conversation and a
    real booking.
    """

    phone = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.phone


class Booking(models.Model):
    """
    Ties everything together. Foreign keys use PROTECT, not CASCADE,
    deleting a business, customer, service, or provider should never
    silently delete booking history. Matches week6/day1-schema-design.md's
    recommended pattern exactly.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        AWAITING_PAYMENT = "awaiting_payment"
        CONFIRMED = "confirmed"
        CANCELLED = "cancelled"
        COMPLETED = "completed"

    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="bookings")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="bookings")

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Captured at booking time, not read from Service.price later - if the
    # business changes their prices next month, old bookings must still show
    # what the customer actually paid, not today's price.
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "date"]),
            models.Index(fields=["customer"]),
        ]

    def __str__(self):
        return f"{self.customer}, {self.service.name} on {self.date} at {self.start_time}"
    

"""
My Notes

Two decisions worth explaining:

PROTECT instead of CASCADE on every foreign key here - deleting a customer, business, service 
or provider should never silently wipe out booking history. Matches week6/day1-schema-design.md's 
recommended pattern exactly.
price_paid is its own field, not derived from service.price - if the business changes prices next month 
a booking made today still needs to show what was actually charged at the time, not today's current 
price.
The indexes are the same concept from Day 2's DSA notes - a B-tree index on (business, date) so 
querying "what's booked for this business on this day" doesn't require scanning every row once the 
table grows.

"""
