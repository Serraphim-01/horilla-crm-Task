"""
Feature registration for Horilla duplicates app.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature

register_feature(
    "duplicate_data",
    "duplicate_models",
    include_models=[
        ("accounts", "Account"),
        ("contacts", "Contact"),
        ("leads", "Lead"),
    ],
)
