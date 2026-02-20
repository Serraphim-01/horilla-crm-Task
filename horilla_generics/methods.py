# Define your horilla_generics helper methods here

from horilla_core.mixins import OwnerQuerysetMixin
from horilla_generics.forms import HorillaModelForm


def get_dynamic_form_for_model(model):
    _model = model  # capture explicitly before class definition

    class ResolvedDynamicForm(OwnerQuerysetMixin, HorillaModelForm):
        class Meta:
            model = _model  # use the captured local variable
            fields = "__all__"
            exclude = [
                "created_at",
                "updated_at",
                "created_by",
                "updated_by",
                "additional_info",
            ]

    return ResolvedDynamicForm
