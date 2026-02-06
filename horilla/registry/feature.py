# horilla_core/registry.py
"""
Feature registry system for Horilla.

This module provides a centralized registry to dynamically associate
Django models with application features such as import, export,
global search, and other pluggable capabilities.
"""

import logging
from collections import defaultdict

from django.apps import apps

logger = logging.getLogger(__name__)

FEATURE_REGISTRY = defaultdict(list)

# Track models registered with all=True and their exclude lists
# Format: {model_class: set(excluded_features)}
ALL_FEATURES_MODELS = {}

# Track models that tried to use features before they were registered
# Format: {feature_name: [model_class, ...]}
PENDING_FEATURE_MODELS = defaultdict(list)

# Track which app registered which feature (for auto-exclusion)
# Format: {feature_name: app_label}
FEATURE_REGISTERING_APP = {}

# Track feature-specific include models (for selective registration)
# Format: {feature_name: [model_class, ...]}
FEATURE_INCLUDE_MODELS = {}

# Track feature-specific exclude models (for excluding from auto-registration)
# Format: {feature_name: [model_class, ...]}
FEATURE_EXCLUDE_MODELS = {}

# Track whether features should auto-register all=True models
# Format: {feature_name: bool}
FEATURE_AUTO_REGISTER_ALL = {}

# Feature configuration mapping: feature_name -> registry_key
# Core features are defined here, but apps can register additional features
# using register_feature() without modifying this file
FEATURE_CONFIG = {
    "import_data": "import_models",
    "export_data": "export_models",
    "global_search": "global_search_models",
}


def register_feature(
    feature_name,
    registry_key=None,
    exclude_app_label=None,
    auto_register_all=None,  # None means auto-detect based on include_models
    include_models=None,
    exclude_models=None,
):
    """
    Register a new feature dynamically from any app.

    Args:
        feature_name: Feature name (e.g., "workflow", "notification")
        registry_key: Registry key in FEATURE_REGISTRY (defaults to "{feature_name}_models")
        exclude_app_label: App label to exclude from auto-registration (e.g., the app registering this feature).
                          If None, will attempt to auto-detect from the calling module.
        auto_register_all: If True, automatically register all models with all=True.
                          If False, only register models specified in include_models.
                          If None (default), automatically set to False when include_models is provided,
                          otherwise defaults to True (auto-register all all=True models).
        include_models: List of specific models to register. Can be:
                       - List of tuples: [("app_label", "model_name"), ...]
                       - List of model classes: [ModelClass, ...]
                       - List of strings: ["app_label.model_name", ...]
                       If provided, only these models will be registered (overrides auto_register_all).
        exclude_models: List of specific models to exclude from auto-registration when auto_register_all=True.
                       Can be:
                       - List of tuples: [("app_label", "model_name"), ...]
                       - List of model classes: [ModelClass, ...]
                       - List of strings: ["app_label.model_name", ...]
                       - Single tuple, model class, or string (will be converted to list)
                       Only works when auto_register_all=True.

    Example:
        # Basic registration (auto-registers all all=True models)
        register_feature("workflow")

        # Selective registration - only specific models
        # auto_register_all is automatically False when include_models is provided
        register_feature(
            "duplicate_data",
            "duplicate_models",
            exclude_app_label="horilla_duplicates",
            include_models=[
                ("horilla_core","User")
            ]
        )

        # Auto-register all=True models but exclude specific ones
        register_feature(
            "notification_template",
            "notification_template_models",
            auto_register_all=True,
            exclude_models=[
                ("horilla_core", "User"),  # Exclude this model
            ],

        )

    Returns:
        bool: True if registered, False if already exists
    """
    import inspect

    if registry_key is None:
        registry_key = f"{feature_name}_models"

    # Auto-determine auto_register_all if not explicitly set
    if auto_register_all is None:
        # If include_models is provided, default to selective registration (False)
        # If include_models is NOT provided, default to True (auto-register all all=True models)
        auto_register_all = False if include_models else True

    # Auto-detect app_label from calling module if not provided
    if exclude_app_label is None:
        try:
            # Get the frame of the caller (skip this function and register_feature)
            frame = inspect.currentframe()
            caller_frame = frame.f_back
            if caller_frame:
                caller_file = caller_frame.f_globals.get("__file__", "")
                if caller_file:
                    # Extract app label from file path
                    # e.g., /path/to/horilla_duplicates/registration.py -> horilla_duplicates
                    path_parts = caller_file.replace("\\", "/").split("/")
                    for i, part in enumerate(path_parts):
                        if part.endswith(".py") and i > 0:
                            # Check if previous part looks like an app label
                            potential_app = path_parts[i - 1]
                            if potential_app.startswith(
                                "horilla_"
                            ) or potential_app.startswith("apps_"):
                                exclude_app_label = potential_app
                                break
        except Exception as e:
            logger.debug("Could not auto-detect app_label for feature exclusion: %s", e)

    # Auto-determine auto_register_all if not explicitly set
    if auto_register_all is None:
        # If include_models is provided, default to selective registration (False)
        # If include_models is NOT provided, default to True (auto-register all all=True models)
        auto_register_all = False if include_models else True

    if feature_name in FEATURE_CONFIG:
        logger.warning(
            "Feature '%s' is already registered. "
            "Overwriting registry key from '%s' to '%s'",
            feature_name,
            FEATURE_CONFIG[feature_name],
            registry_key,
        )
        # Store old registry key before updating
        old_registry_key = FEATURE_CONFIG[feature_name]

        FEATURE_CONFIG[feature_name] = registry_key
        FEATURE_AUTO_REGISTER_ALL[feature_name] = auto_register_all

        # If switching to selective registration, clear existing models from registry
        if not auto_register_all:
            # Clear from old registry key
            if old_registry_key in FEATURE_REGISTRY:
                FEATURE_REGISTRY[old_registry_key].clear()
                logger.info(
                    "Cleared existing models from feature '%s' registry (key: '%s') for selective registration",
                    feature_name,
                    old_registry_key,
                )
            # Also clear from new registry key if it's different
            if registry_key != old_registry_key and registry_key in FEATURE_REGISTRY:
                FEATURE_REGISTRY[registry_key].clear()
                logger.info(
                    "Cleared existing models from feature '%s' registry (key: '%s') for selective registration",
                    feature_name,
                    registry_key,
                )

        # Update exclude app if provided
        if exclude_app_label:
            FEATURE_REGISTERING_APP[feature_name] = exclude_app_label
        # Update include models if provided
        if include_models:
            # Process include_models (same logic as below)
            included_model_classes = []
            for model_spec in include_models:
                model_class = None
                if isinstance(model_spec, tuple) and len(model_spec) == 2:
                    app_label, model_name = model_spec
                    try:
                        model_class = apps.get_model(app_label, model_name)
                    except LookupError:
                        continue
                elif isinstance(model_spec, str) and "." in model_spec:
                    try:
                        app_label, model_name = model_spec.split(".", 1)
                        model_class = apps.get_model(app_label, model_name)
                    except (ValueError, LookupError):
                        continue
                elif hasattr(model_spec, "_meta"):
                    model_class = model_spec

                if model_class and model_class not in included_model_classes:
                    included_model_classes.append(model_class)
            FEATURE_INCLUDE_MODELS[feature_name] = included_model_classes

            # Register only the included models
            excluded_app = FEATURE_REGISTERING_APP.get(feature_name)
            for model_class in included_model_classes:
                # Skip if model belongs to the excluded app
                if excluded_app and model_class._meta.app_label == excluded_app:
                    continue
                if model_class not in FEATURE_REGISTRY[registry_key]:
                    FEATURE_REGISTRY[registry_key].append(model_class)

        # Update exclude models if provided
        if exclude_models:
            # Process exclude_models (same logic as below)
            excluded_model_classes = []
            if not isinstance(exclude_models, list):
                exclude_models = [exclude_models]

            for model_spec in exclude_models:
                model_class = None
                if isinstance(model_spec, tuple) and len(model_spec) == 2:
                    app_label, model_name = model_spec
                    try:
                        model_class = apps.get_model(app_label, model_name)
                    except LookupError:
                        continue
                elif isinstance(model_spec, str) and "." in model_spec:
                    try:
                        app_label, model_name = model_spec.split(".", 1)
                        model_class = apps.get_model(app_label, model_name)
                    except (ValueError, LookupError):
                        continue
                elif hasattr(model_spec, "_meta"):
                    model_class = model_spec

                if model_class and model_class not in excluded_model_classes:
                    excluded_model_classes.append(model_class)

            FEATURE_EXCLUDE_MODELS[feature_name] = excluded_model_classes

            # Remove excluded models from registry
            excluded_app = FEATURE_REGISTERING_APP.get(feature_name)
            for model_class in excluded_model_classes:
                if model_class in FEATURE_REGISTRY[registry_key]:
                    FEATURE_REGISTRY[registry_key].remove(model_class)
                    logger.debug(
                        "Removed excluded model %s from feature '%s' registry",
                        model_class,
                        feature_name,
                    )
        return False

    FEATURE_CONFIG[feature_name] = registry_key
    FEATURE_AUTO_REGISTER_ALL[feature_name] = auto_register_all

    if exclude_app_label:
        FEATURE_REGISTERING_APP[feature_name] = exclude_app_label

    # Process include_models if provided
    included_model_classes = []
    if include_models:
        for model_spec in include_models:
            model_class = None
            if isinstance(model_spec, tuple) and len(model_spec) == 2:
                # Tuple format: ("app_label", "model_name")
                app_label, model_name = model_spec
                try:
                    model_class = apps.get_model(app_label, model_name)
                except LookupError as e:
                    logger.warning(
                        "Could not find model '%s.%s' for feature '%s': %s",
                        app_label,
                        model_name,
                        feature_name,
                        e,
                    )
                    continue
            elif isinstance(model_spec, str):
                # String format: "app_label.model_name"
                if "." in model_spec:
                    try:
                        app_label, model_name = model_spec.split(".", 1)
                        model_class = apps.get_model(app_label, model_name)
                    except (ValueError, LookupError) as e:
                        logger.warning(
                            "Could not parse or find model '%s' for feature '%s': %s",
                            model_spec,
                            feature_name,
                            e,
                        )
                        continue
            elif hasattr(model_spec, "_meta"):
                # Model class directly
                model_class = model_spec
            else:
                logger.warning(
                    "Invalid model specification '%s' for feature '%s'. "
                    "Expected tuple, string, or model class.",
                    model_spec,
                    feature_name,
                )
                continue

            if model_class and model_class not in included_model_classes:
                included_model_classes.append(model_class)

        FEATURE_INCLUDE_MODELS[feature_name] = included_model_classes
        logger.info(
            "Registered new feature '%s' -> '%s' with %s specific models",
            feature_name,
            registry_key,
            len(included_model_classes),
        )
    else:
        FEATURE_INCLUDE_MODELS[feature_name] = []

    # Process exclude_models if provided
    excluded_model_classes = []
    if exclude_models:
        # Handle single model (not a list) - convert to list
        if not isinstance(exclude_models, list):
            exclude_models = [exclude_models]

        for model_spec in exclude_models:
            model_class = None
            if isinstance(model_spec, tuple) and len(model_spec) == 2:
                # Tuple format: ("app_label", "model_name")
                app_label, model_name = model_spec
                try:
                    model_class = apps.get_model(app_label, model_name)
                except LookupError as e:
                    logger.warning(
                        "Could not find model '%s.%s' to exclude from feature '%s': %s",
                        app_label,
                        model_name,
                        feature_name,
                        e,
                    )
                    continue
            elif isinstance(model_spec, str):
                # String format: "app_label.model_name"
                if "." in model_spec:
                    try:
                        app_label, model_name = model_spec.split(".", 1)
                        model_class = apps.get_model(app_label, model_name)
                    except (ValueError, LookupError) as e:
                        logger.warning(
                            "Could not parse or find model '%s' to exclude from feature '%s': %s",
                            model_spec,
                            feature_name,
                            e,
                        )
                        continue
            elif hasattr(model_spec, "_meta"):
                # Model class directly
                model_class = model_spec
            else:
                logger.warning(
                    "Invalid model specification '%s' to exclude from feature '%s'. "
                    "Expected tuple, string, or model class.",
                    model_spec,
                    feature_name,
                )
                continue

            if model_class and model_class not in excluded_model_classes:
                excluded_model_classes.append(model_class)

        FEATURE_EXCLUDE_MODELS[feature_name] = excluded_model_classes
        logger.info(
            "Registered %s models to exclude from feature '%s'",
            len(excluded_model_classes),
            feature_name,
        )
    else:
        FEATURE_EXCLUDE_MODELS[feature_name] = []

    # Log registration
    log_parts = [f"Registered new feature '{feature_name}' -> '{registry_key}'"]
    if exclude_app_label:
        log_parts.append(f"excluding app '{exclude_app_label}'")
    if not auto_register_all:
        log_parts.append("with selective registration")
    logger.info(", ".join(log_parts))

    # Register models based on configuration
    excluded_app = FEATURE_REGISTERING_APP.get(feature_name)

    # First, register explicitly included models
    for model_class in FEATURE_INCLUDE_MODELS.get(feature_name, []):
        # Skip if model belongs to the excluded app
        if excluded_app and model_class._meta.app_label == excluded_app:
            logger.debug(
                "Skipping registration of model %s for feature '%s' (model belongs to excluded app '%s')",
                model_class,
                feature_name,
                excluded_app,
            )
            continue

        if model_class not in FEATURE_REGISTRY[registry_key]:
            FEATURE_REGISTRY[registry_key].append(model_class)
            logger.debug(
                "Registered model %s for feature '%s' (explicitly included)",
                model_class,
                feature_name,
            )

    # Remove excluded models from registry (if they were already registered)
    excluded_models = FEATURE_EXCLUDE_MODELS.get(feature_name, [])
    for model_class in excluded_models:
        if model_class in FEATURE_REGISTRY[registry_key]:
            FEATURE_REGISTRY[registry_key].remove(model_class)
            logger.debug(
                "Removed excluded model %s from feature '%s' registry",
                model_class,
                feature_name,
            )

    # If selective registration is enabled, clean up any models that shouldn't be there
    if not auto_register_all:
        included_models = set(FEATURE_INCLUDE_MODELS.get(feature_name, []))
        models_to_remove = []
        for model_class in FEATURE_REGISTRY[registry_key]:
            # Remove if not in included models
            if model_class not in included_models:
                # Also check if it belongs to excluded app
                if excluded_app and model_class._meta.app_label == excluded_app:
                    models_to_remove.append(model_class)
                elif model_class not in included_models:
                    models_to_remove.append(model_class)

        for model_class in models_to_remove:
            FEATURE_REGISTRY[registry_key].remove(model_class)
            logger.debug(
                "Removed model %s from feature '%s' (not in include_models for selective registration)",
                model_class,
                feature_name,
            )

    # Then, auto-register all=True models if enabled
    if auto_register_all:
        # Get excluded models for this feature
        excluded_models = FEATURE_EXCLUDE_MODELS.get(feature_name, [])

        for model_class, excluded_features in ALL_FEATURES_MODELS.items():
            # Skip if model belongs to the excluded app
            if excluded_app and model_class._meta.app_label == excluded_app:
                logger.debug(
                    "Skipping auto-registration of model %s for feature '%s' (model belongs to excluded app '%s')",
                    model_class,
                    feature_name,
                    excluded_app,
                )
                continue

            # Skip if already registered via include_models
            if model_class in FEATURE_INCLUDE_MODELS.get(feature_name, []):
                continue

            # Skip if model is in the exclude_models list
            if model_class in excluded_models:
                logger.debug(
                    "Skipping auto-registration of model %s for feature '%s' (model is in exclude_models)",
                    model_class,
                    feature_name,
                )
                # Remove from registry if it was already registered
                if model_class in FEATURE_REGISTRY[registry_key]:
                    FEATURE_REGISTRY[registry_key].remove(model_class)
                    logger.debug(
                        "Removed excluded model %s from feature '%s' registry",
                        model_class,
                        feature_name,
                    )
                continue

            # Skip if feature is in the model's exclude list
            if feature_name not in excluded_features:
                if model_class not in FEATURE_REGISTRY[registry_key]:
                    FEATURE_REGISTRY[registry_key].append(model_class)
                    logger.debug(
                        "Auto-registered model %s for new feature '%s' (was registered with all=True)",
                        model_class,
                        feature_name,
                    )

    # Register models that tried to use this feature before it was registered
    if feature_name in PENDING_FEATURE_MODELS:
        for model_class in PENDING_FEATURE_MODELS[feature_name]:
            if model_class not in FEATURE_REGISTRY[registry_key]:
                FEATURE_REGISTRY[registry_key].append(model_class)
                logger.debug(
                    "Registered model %s for feature '%s' (was pending before feature registration)",
                    model_class.__name__,
                    feature_name,
                )
        # Clear pending list for this feature
        del PENDING_FEATURE_MODELS[feature_name]

    return True


def register_model_for_feature(
    model_class=None,
    app_label=None,
    model_name=None,
    features=None,
    all=False,
    exclude=None,
    **kwargs,
):
    """
    Register an existing model for specific features without modifying the model file.

    Args:
        model_class: Model class (optional if app_label/model_name provided)
        app_label: App label (e.g., "horilla_core")
        model_name: Model name (e.g., "User")
        features: Feature name(s) as list or string
        all: Enable all features if True
        exclude: Features to exclude when all=True
        **kwargs: Legacy boolean flags (global_search=True, etc.)

    Example:
        register_model_for_feature(
            app_label="horilla_core",
            model_name="User",
            features=["global_search"]
        )
        register_model_for_feature(
            app_label="horilla_calendar",
            model_name="Event",
            all=True
        )

    Returns:
        bool: True if registered, False otherwise
    """
    # Determine which model to register
    if model_class is None:
        if app_label is None or model_name is None:
            logger.error(
                "register_model_for_feature: Must provide either model_class or both "
                "app_label and model_name"
            )
            return False

        try:
            model_class = apps.get_model(app_label, model_name)
        except LookupError as e:
            logger.error(
                "register_model_for_feature: Model '%s.%s' not found: %s",
                app_label,
                model_name,
                e,
            )
            return False
    else:
        # Use model class directly
        app_label = model_class._meta.app_label
        model_name = model_class.__name__

    # Determine which features to enable
    enabled_features = set()
    exclude_set = set()

    # Handle 'all' flag - enable all features
    if all:
        # Track this model in ALL_FEATURES_MODELS for future feature auto-registration
        if exclude is not None:
            exclude_list = [exclude] if isinstance(exclude, str) else exclude
            exclude_set = set(exclude_list)
        ALL_FEATURES_MODELS[model_class] = exclude_set

        # Enable all currently registered features
        enabled_features.update(FEATURE_CONFIG.keys())

    # New way: using features parameter
    if features is not None:
        if isinstance(features, str):
            features = [features]
        enabled_features.update(features)

    # Legacy way: check boolean keyword arguments
    legacy_features = {
        "import_data": kwargs.get("import_data", False),
        "export_data": kwargs.get("export_data", False),
        "global_search": kwargs.get("global_search", False),
    }

    for feature_name, enabled in legacy_features.items():
        if enabled:
            enabled_features.add(feature_name)

    # Check kwargs for any dynamically registered features
    for feature_name, enabled in kwargs.items():
        if enabled and isinstance(enabled, bool) and enabled:
            if feature_name in FEATURE_CONFIG:
                enabled_features.add(feature_name)

    # Apply exclusions
    if exclude is not None:
        if isinstance(exclude, str):
            exclude = [exclude]
        enabled_features -= set(exclude)

    if not enabled_features:
        logger.warning(
            "register_model_for_feature: No features specified for model %s.%s",
            app_label,
            model_name,
        )
        # Even if no features to register now, return True if all=True (for tracking)
        return all

    # Register model for each enabled feature
    registered = False
    for feature_name in enabled_features:
        if feature_name in FEATURE_CONFIG:
            # Check if this feature has selective registration enabled
            # If auto_register_all=False, only register if model is in include_models
            if not FEATURE_AUTO_REGISTER_ALL.get(feature_name, True):
                # Feature has selective registration - check if model is included
                included_models = FEATURE_INCLUDE_MODELS.get(feature_name, [])
                if model_class not in included_models:
                    logger.debug(
                        "Skipping registration of model %s.%s for feature '%s' "
                        "(feature has selective registration and model not in include_models)",
                        app_label,
                        model_name,
                        feature_name,
                    )
                    continue

            registry_key = FEATURE_CONFIG[feature_name]

            # Check if model belongs to excluded app
            excluded_app = FEATURE_REGISTERING_APP.get(feature_name)
            if excluded_app and model_class._meta.app_label == excluded_app:
                logger.debug(
                    "Skipping registration of model %s.%s for feature '%s' "
                    "(model belongs to excluded app '%s')",
                    app_label,
                    model_name,
                    feature_name,
                    excluded_app,
                )
                continue

            if model_class not in FEATURE_REGISTRY[registry_key]:
                FEATURE_REGISTRY[registry_key].append(model_class)
                registered = True
                logger.info(
                    "Registered model %s.%s for feature '%s'",
                    app_label,
                    model_name,
                    feature_name,
                )
            else:
                logger.debug(
                    "Model %s.%s already registered for feature '%s'",
                    app_label,
                    model_name,
                    feature_name,
                )
        else:
            logger.warning(
                "Unknown feature '%s' for model %s.%s. Make sure to register it using register_feature('%s')",
                feature_name,
                app_label,
                model_name,
                feature_name,
            )

    return registered


def register_models_for_feature(
    models, features=None, all=False, exclude=None, **kwargs
):
    """
    Register multiple models at once with the same features.

    Args:
        models: List of models as tuples [("app_label", "model_name")],
                model classes, or dicts [{"app_label": "...", "model_name": "..."}]
        features: Feature name(s) as list or string
        all: Enable all features if True
        exclude: Features to exclude when all=True
        **kwargs: Legacy boolean flags

    Example:
        register_models_for_feature(
            models=[
                ("horilla_core", "User"),
                ("horilla_activity", "Activity"),
                ("horilla_calendar", "Event"),
            ],
            features=["global_search", "import_data"]
        )
        register_models_for_feature(
            models=[("horilla_core", "User"), ("horilla_activity", "Activity")],
            all=True,
            exclude=["export_data"]
        )

    Returns:
        dict: Summary with "registered", "failed", and "total" keys
    """
    registered_models = []
    failed_models = []

    # Normalize models list
    normalized_models = []
    for model in models:
        if isinstance(model, tuple) and len(model) == 2:
            # Tuple format: (app_label, model_name)
            normalized_models.append({"app_label": model[0], "model_name": model[1]})
        elif isinstance(model, dict):
            # Dict format: {"app_label": "...", "model_name": "..."}
            normalized_models.append(model)
        else:
            # Assume it's a model class
            try:
                normalized_models.append({"model_class": model})
            except Exception:
                failed_models.append(str(model))
                logger.error(
                    "register_models_for_feature: Invalid model format: %s",
                    model,
                )
                continue

    # Register each model
    for model_info in normalized_models:
        try:
            if "model_class" in model_info:
                # Use model class directly
                result = register_model_for_feature(
                    model_class=model_info["model_class"],
                    features=features,
                    all=all,
                    exclude=exclude,
                    **kwargs,
                )
                model_identifier = f"{model_info['model_class']._meta.app_label}.{model_info['model_class'].__name__}"
            else:
                # Use app_label and model_name
                result = register_model_for_feature(
                    app_label=model_info["app_label"],
                    model_name=model_info["model_name"],
                    features=features,
                    all=all,
                    exclude=exclude,
                    **kwargs,
                )
                model_identifier = (
                    f"{model_info['app_label']}.{model_info['model_name']}"
                )

            if result:
                registered_models.append(model_identifier)
            else:
                failed_models.append(model_identifier)

        except Exception as e:
            model_identifier = str(model_info)
            failed_models.append(model_identifier)
            logger.error(
                "register_models_for_feature: Failed to register %s: %s",
                model_identifier,
                e,
            )

    result_summary = {
        "registered": registered_models,
        "failed": failed_models,
        "total": len(normalized_models),
    }

    logger.info(
        "register_models_for_feature: Registered %s/%s models",
        len(registered_models),
        len(normalized_models),
    )

    return result_summary


def feature_enabled(
    *,
    all=False,
    features=None,
    exclude=None,
    import_data=False,
    export_data=False,
    global_search=False,
    **kwargs,
):
    """
    Decorator to register models for specific features.

    Supports both core features and dynamically registered features.

    Example:
        @feature_enabled(features=["import_data", "export_data"])
        @feature_enabled(all=True, exclude=["import_data"])
        @feature_enabled(global_search=True)
        @feature_enabled(global_search=True, dashboard_component=True)  # Works for dynamically registered features
        @feature_enabled(mail_template=True, activity_related=True)  # Works for dynamically registered features
    """

    def decorator(model_class):
        # Determine which features to enable
        enabled_features = set()

        # Track exclude list for all=True models
        exclude_set = set()

        # New way: using features parameter (list of strings)
        if features is not None:
            features_list = [features] if isinstance(features, str) else features
            enabled_features.update(features_list)

        # Backward compatibility: check old keyword arguments
        legacy_features = {
            "import_data": import_data,
            "export_data": export_data,
            "global_search": global_search,
        }

        # If any legacy features are explicitly set, add them
        for feature_name, enabled in legacy_features.items():
            if enabled:
                enabled_features.add(feature_name)

        # Check kwargs for any dynamically registered features
        # Any kwargs that are True and exist in FEATURE_CONFIG are treated as feature flags
        for feature_name, enabled in kwargs.items():
            if enabled and isinstance(enabled, bool) and enabled:
                # Check if this is a registered feature
                if feature_name in FEATURE_CONFIG:
                    enabled_features.add(feature_name)
                else:
                    # Feature not registered yet - track it for later registration
                    if model_class not in PENDING_FEATURE_MODELS[feature_name]:
                        PENDING_FEATURE_MODELS[feature_name].append(model_class)
                    logger.debug(
                        "Feature '%s' not yet registered for model %s. Will register when feature is registered.",
                        feature_name,
                        model_class.__name__,
                    )

        # Handle 'all' flag
        if all:
            # Track this model for future feature registrations
            exclude_list = []
            if exclude is not None:
                exclude_list = [exclude] if isinstance(exclude, str) else exclude
            exclude_set = set(exclude_list)
            ALL_FEATURES_MODELS[model_class] = exclude_set

            enabled_features.update(FEATURE_CONFIG.keys())

        # Apply exclusions
        enabled_features -= exclude_set

        # Register model for each enabled feature
        for feature_name in enabled_features:
            if feature_name in FEATURE_CONFIG:
                registry_key = FEATURE_CONFIG[feature_name]
                if model_class not in FEATURE_REGISTRY[registry_key]:
                    FEATURE_REGISTRY[registry_key].append(model_class)
            else:
                logger.warning(
                    "Unknown feature '%s' for model %s. Make sure to register it using register_feature('%s') "
                    "in your app's ready() method or models.py",
                    feature_name,
                    model_class.__name__,
                    feature_name,
                )

        return model_class

    return decorator
