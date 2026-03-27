"""
Filters for the horilla_duplicates app
"""

# Third-party imports (Django)
import django_filters

# First-party / Horilla apps
from horilla_core.models import HorillaContentType
from horilla_generics.filters import HorillaFilterSet

from .models import DuplicateRule, MatchingRule


class MatchingRuleFilter(HorillaFilterSet):
    """
    Filter for MatchingRule
    """

    content_type = django_filters.ModelChoiceFilter(
        queryset=HorillaContentType.objects.all(),
        field_name="content_type",
    )

    class Meta:
        """Meta options for MatchingRuleFilter."""

        model = MatchingRule
        fields = ["content_type"]
        search_fields = ["name", "description"]


class DuplicateRuleFilter(HorillaFilterSet):
    """
    Filter for DuplicateRule
    """

    content_type = django_filters.ModelChoiceFilter(
        queryset=HorillaContentType.objects.all(),
        field_name="content_type",
    )
    matching_rule = django_filters.ModelChoiceFilter(
        queryset=MatchingRule.objects.all(),
        field_name="matching_rule",
    )

    class Meta:
        """Meta options for DuplicateRuleFilter."""

        model = DuplicateRule
        fields = ["content_type", "matching_rule"]
        search_fields = ["name", "description"]
