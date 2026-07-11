from django.contrib import admin

from .models import Booking, Business, Customer, Provider, Service


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "whatsapp_number", "opens_at", "closes_at")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "price", "duration_minutes", "is_active")
    list_filter = ("business", "is_active")


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "is_active")
    list_filter = ("business", "is_active")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "created_at")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("customer", "service", "provider", "date", "start_time", "status")
    list_filter = ("business", "status", "date")
