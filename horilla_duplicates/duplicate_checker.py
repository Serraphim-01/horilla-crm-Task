"""
Utility functions for checking duplicates
"""

# First party imports (Horilla)
from horilla.db.models import ForeignKey, OneToOneField, Q

# First-party / Horilla apps
from horilla_core.models import HorillaContentType
from horilla_duplicates.models import DuplicateRule


def check_duplicates(instance, is_edit=False):
    """
    Check for potential duplicates based on duplicate rules.

    Args:
        instance: Model instance to check (before saving)
        is_edit: Whether this is an edit operation (True) or create (False)

    Returns:
        dict with keys:
            - has_duplicates: bool
            - duplicate_rule: DuplicateRule instance or None
            - duplicate_records: list of duplicate record instances
            - alert_title: str
            - alert_message: str
    """
    if not instance or not instance._meta.model:
        return {
            "has_duplicates": False,
            "duplicate_rule": None,
            "duplicate_records": [],
            "alert_title": "",
            "alert_message": "",
        }

    # Get model name
    model_name = instance._meta.model_name.lower()

    # Get content type for this model
    try:
        # Try to find HorillaContentType
        try:
            content_type = HorillaContentType.objects.get(model=model_name)
        except HorillaContentType.DoesNotExist:
            content_type = HorillaContentType.objects.filter(model=model_name).first()
            if not content_type:
                return {
                    "has_duplicates": False,
                    "duplicate_rule": None,
                    "duplicate_records": [],
                    "alert_title": "",
                    "alert_message": "",
                }
    except Exception:
        return {
            "has_duplicates": False,
            "duplicate_rule": None,
            "duplicate_records": [],
            "alert_title": "",
            "alert_message": "",
        }

    # Get duplicate rules for this content type
    duplicate_rules = DuplicateRule.objects.filter(content_type=content_type)

    if not duplicate_rules.exists():
        return {
            "has_duplicates": False,
            "duplicate_rule": None,
            "duplicate_records": [],
            "alert_title": "",
            "alert_message": "",
        }

    # Check each duplicate rule
    for duplicate_rule in duplicate_rules:
        # Check if rule applies to this operation (create or edit)
        # We should check for duplicates regardless of action (allow/block)
        # The action only affects the UI behavior, not whether we check for duplicates
        action_field = (
            duplicate_rule.action_on_edit
            if is_edit
            else duplicate_rule.action_on_create
        )
        if action_field == "allow":
            # Allow action - show warning but don't block
            pass
        elif action_field == "block":
            # Block action - still check for duplicates, but will block save if found
            pass
        else:
            # Unknown action - skip this rule
            continue

        # Get matching rule
        matching_rule = duplicate_rule.matching_rule

        # Check conditions (if any)
        if duplicate_rule.conditions.exists():
            conditions_met = evaluate_rule_conditions(duplicate_rule, instance)
            if not conditions_met:
                continue  # Skip this rule if conditions not met

        # Find duplicates using matching rule
        duplicate_records = find_duplicates_by_matching_rule(
            instance, matching_rule, exclude_pk=instance.pk if instance.pk else None
        )

        if duplicate_records:
            # Get the action for this operation (create or edit)
            action = (
                duplicate_rule.action_on_edit
                if is_edit
                else duplicate_rule.action_on_create
            )
            return {
                "has_duplicates": True,
                "duplicate_rule": duplicate_rule,
                "duplicate_records": duplicate_records,
                "alert_title": duplicate_rule.alert_title,
                "alert_message": duplicate_rule.alert_message,
                "show_duplicate_records": duplicate_rule.show_duplicate_records,
                "action": action,  # 'allow' or 'block'
            }

    return {
        "has_duplicates": False,
        "duplicate_rule": None,
        "duplicate_records": [],
        "alert_title": "",
        "alert_message": "",
    }


def evaluate_rule_conditions(duplicate_rule, instance):
    """
    Evaluate if duplicate rule conditions are met for the instance.

    Returns:
        bool: True if conditions are met, False otherwise
    """
    conditions = duplicate_rule.conditions.all().order_by("order", "created_at")
    if not conditions.exists():
        return True  # No conditions means always apply

    result = None
    previous_logical_op = None

    for condition in conditions:
        field_name = condition.field
        operator = condition.operator
        value = condition.value
        logical_operator = condition.logical_operator

        try:
            field_value = getattr(instance, field_name, None)
            if field_value is None:
                field_value = ""

            # Convert to string for comparison
            field_value_str = str(field_value)
            value_str = str(value) if value else ""

            # Evaluate condition
            condition_result = False
            if operator == "equals":
                condition_result = field_value_str.lower() == value_str.lower()
            elif operator == "not_equals":
                condition_result = field_value_str.lower() != value_str.lower()
            elif operator == "contains":
                condition_result = value_str.lower() in field_value_str.lower()
            elif operator == "not_contains":
                condition_result = value_str.lower() not in field_value_str.lower()
            elif operator == "starts_with":
                condition_result = field_value_str.lower().startswith(value_str.lower())
            elif operator == "ends_with":
                condition_result = field_value_str.lower().endswith(value_str.lower())
            elif operator == "empty":
                condition_result = not field_value or field_value_str.strip() == ""
            elif operator == "not_empty":
                condition_result = bool(field_value) and field_value_str.strip() != ""

            # Combine with previous result
            if result is None:
                result = condition_result
            else:
                if previous_logical_op == "and":
                    result = result and condition_result
                elif previous_logical_op == "or":
                    result = result or condition_result

            previous_logical_op = logical_operator

        except Exception:
            # If error evaluating condition, skip it
            continue

    return result if result is not None else True


def find_duplicates_by_matching_rule(instance, matching_rule, exclude_pk=None):
    """
    Find duplicate records using a matching rule.

    Args:
        instance: Model instance to check
        matching_rule: MatchingRule instance
        exclude_pk: PK to exclude from results (usually the current instance)

    Returns:
        QuerySet of duplicate records
    """
    Model = instance._meta.model
    criteria = matching_rule.criteria.all().order_by("order", "created_at")

    if not criteria.exists():
        return Model.objects.none()

    # Build query based on criteria
    query = Q()
    for criterion in criteria:
        field_name = criterion.field_name
        matching_method = criterion.matching_method
        match_blank_fields = criterion.match_blank_fields

        try:
            field_value = getattr(instance, field_name, None)

            # Skip if field is blank and match_blank_fields is False
            if not field_value and not match_blank_fields:
                continue

            # Build field query based on matching method
            if matching_method == "exact":
                if field_value is None or (
                    isinstance(field_value, str) and field_value.strip() == ""
                ):
                    if match_blank_fields:
                        field_query = Q(**{f"{field_name}__isnull": True}) | Q(
                            **{f"{field_name}": ""}
                        )
                    else:
                        continue
                else:
                    # Check field type
                    field = Model._meta.get_field(field_name)
                    # Properly check if it's a ForeignKey or OneToOneField
                    if isinstance(field, (ForeignKey, OneToOneField)):
                        # It's a related field, use _id suffix
                        if hasattr(field_value, "pk"):
                            field_query = Q(**{f"{field_name}_id": field_value.pk})
                        else:
                            field_query = Q(**{f"{field_name}_id": field_value})
                    else:
                        # Regular field, use field name directly
                        field_query = Q(**{field_name: field_value})
            elif matching_method == "fuzzy":
                # For fuzzy matching, use icontains (simple implementation)
                if field_value and isinstance(field_value, str):
                    field_query = Q(**{f"{field_name}__icontains": field_value})
                else:
                    continue
            else:
                # Default to exact
                if field_value is None:
                    field_query = Q(**{f"{field_name}__isnull": True})
                else:
                    field = Model._meta.get_field(field_name)
                    # Properly check if it's a ForeignKey or OneToOneField
                    if isinstance(field, (ForeignKey, OneToOneField)):
                        # It's a related field, use _id suffix
                        if hasattr(field_value, "pk"):
                            field_query = Q(**{f"{field_name}_id": field_value.pk})
                        else:
                            field_query = Q(**{f"{field_name}_id": field_value})
                    else:
                        # Regular field, use field name directly
                        field_query = Q(**{field_name: field_value})

            # Combine queries with AND (all criteria must match)
            if query:
                query = query & field_query
            else:
                query = field_query

        except Exception:
            # Skip fields that don't exist or cause errors
            continue

    if not query:
        return Model.objects.none()

    # Exclude current instance if editing
    queryset = Model.objects.filter(query)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)

    # Return all duplicates - pagination will be handled by the view if needed
    return queryset
