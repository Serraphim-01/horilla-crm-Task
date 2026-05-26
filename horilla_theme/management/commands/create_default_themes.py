# Third-party imports (Django)
from django.core.management.base import BaseCommand

# First-party / Horilla apps
from horilla_theme.models import HorillaColorTheme
from horilla_theme.utils import THEMES_DATA


class Command(BaseCommand):
    help = "Create default color themes for the CRM"

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset and recreate all themes',
        )

    def handle(self, *args, **options):
        reset = options.get('reset', False)
        
        if reset:
            self.stdout.write("Resetting themes...")
            HorillaColorTheme.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("All themes deleted."))

        # Check if themes already exist
        if not reset and HorillaColorTheme.objects.exists():
            self.stdout.write(
                self.style.WARNING("Themes already exist. Use --reset to recreate them.")
            )
            self.stdout.write("Ensuring default theme is set...")
            try:
                HorillaColorTheme.ensure_single_default()
                self.stdout.write(self.style.SUCCESS("Default theme ensured."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error ensuring default theme: {e}"))
            return

        created_count = 0
        self.stdout.write("Creating default color themes...")

        for theme_data in THEMES_DATA:
            try:
                is_default = theme_data.get("is_default", False)

                defaults = theme_data.copy()
                defaults["is_default"] = is_default

                theme, created = HorillaColorTheme.objects.get_or_create(
                    name=theme_data["name"],
                    defaults=defaults,
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Created theme: {theme.name}")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"- Theme already exists: {theme.name}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Error creating theme {theme_data["name"]}: {str(e)}'
                    )
                )

        # Ensure only one default theme is set
        try:
            HorillaColorTheme.ensure_single_default()
            self.stdout.write(self.style.SUCCESS("Default theme ensured."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error ensuring default theme: {e}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully created {created_count} themes.")
        )
