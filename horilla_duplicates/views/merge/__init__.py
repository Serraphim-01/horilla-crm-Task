"""horilla_duplicates merge-related views."""


from .generic import GenericDuplicateDetailView, DuplicateWarningModalView
from .potential import PotentialDuplicatesTabView, UpdateMergeButtonView
from .merge_flow import (
    MergeDuplicatesCompareView,
    MergeDuplicatesSummaryView,
    MergeDuplicatesView,
)

__all__ = [
    "GenericDuplicateDetailView",
    "DuplicateWarningModalView",
    "PotentialDuplicatesTabView",
    "UpdateMergeButtonView",
    "MergeDuplicatesCompareView",
    "MergeDuplicatesSummaryView",
    "MergeDuplicatesView",
]
