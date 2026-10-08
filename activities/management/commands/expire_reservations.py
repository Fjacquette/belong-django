"""Optional durable cleanup/promotion; allocation also cleans up synchronously."""
from django.core.management.base import BaseCommand, CommandError
from activities.models import FreeReservationPool
from activities.participation import locked_activity
from activities.reservations import maintain_locked


class Command(BaseCommand):
    help = 'Expire free holds and promote eligible FIFO entries under each Activity lock.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1000)
        parser.add_argument('--after', type=int, default=0, help='Resume after this pool ID when processing a larger deployment.')

    def handle(self, *args, **options):
        if options['limit'] < 1 or options['after'] < 0:
            raise CommandError('Use a positive limit and nonnegative cursor.')
        rows = FreeReservationPool.objects.filter(pk__gt=options['after']).order_by('pk').values_list('pk', 'target__activity_id')[:options['limit']]
        count = 0
        last = options['after']
        for last, pk in list(rows):
            with locked_activity(pk) as activity:
                maintain_locked(activity, activity.registration_target)
            count += 1
        self.stdout.write(f'Processed {count} free reservation pools; last pool ID {last}.')
