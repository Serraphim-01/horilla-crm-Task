"""
Admin registration for the horilla_duplicates app
"""

# Third-party imports (Django)
from django.contrib import admin

# First-party / Horilla apps
from horilla_duplicates.models import DuplicateRule, MatchingRule, MatchingRuleCriteria

# Register your horilla_duplicates models here.


admin.site.register(MatchingRule)
admin.site.register(DuplicateRule)
admin.site.register(MatchingRuleCriteria)
