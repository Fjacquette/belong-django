from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Retired React mock importer; use seed_demo for local demo data."

    def add_arguments(self, parser):
        # Accept legacy flags only so every old invocation receives the same safe error.
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--data")
        parser.add_argument("--images")

    def handle(self, *args, **options):
        raise CommandError("import_mock_activities is retired. Use manage.py seed_demo in local dev/test.")
