from django.core.management.base import BaseCommand, CommandError

from webhooks.models import ConversationEvent
from webhooks.state_machine import State, get_state, resume_bot


class Command(BaseCommand):
    help = "Move a customer out of HUMAN_TAKEOVER, back into the automated flow."

    def add_arguments(self, parser):
        parser.add_argument("phone", type=str, help="Customer's phone number, e.g. 254714585901")

    def handle(self, *args, **options):
        phone = options["phone"]
        current_state = get_state(phone)

        if current_state != State.HUMAN_TAKEOVER:
            raise CommandError(
                f"{phone} is not in HUMAN_TAKEOVER (currently: {current_state}). Nothing to resume."
            )

        restored_state = resume_bot(phone)

        ConversationEvent.objects.create(
            phone=phone,
            direction=ConversationEvent.Direction.OUTBOUND,
            text=f"[Admin resumed the bot. Restored to {restored_state}.]",
            state=restored_state,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Resumed {phone}: bot is active again, restored to {restored_state}.")
        )
