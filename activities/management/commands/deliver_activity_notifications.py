from django.core.management.base import BaseCommand, CommandError
from activities.notifications import drain_notifications


class Command(BaseCommand):
    help = 'Deliver due Activity notices, with cancellation priority and bounded retries.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 1000:
            raise CommandError('limit must be between 1 and 1000')
        self.stdout.write(f"Sent {drain_notifications(options['limit'])} Activity notices.")
