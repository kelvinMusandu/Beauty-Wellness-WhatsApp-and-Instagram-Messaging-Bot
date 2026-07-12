from django.contrib import admin

from .models import ConversationEvent, WebhookEvent


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id", "received_at", "processed")
    list_filter = ("processed",)
    readonly_fields = ("raw_payload", "received_at")


@admin.register(ConversationEvent)
class ConversationEventAdmin(admin.ModelAdmin):
    list_display = ("phone", "direction", "state", "text", "created_at")
    list_filter = ("direction", "state")
    ordering = ("phone", "created_at")
