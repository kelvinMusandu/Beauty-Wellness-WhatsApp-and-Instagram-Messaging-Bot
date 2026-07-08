from django.contrib import admin

from .models import WebhookEvent


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id", "received_at", "processed")
    list_filter = ("processed",)
    readonly_fields = ("raw_payload", "received_at")
