"""Maps internal ReviewState (a read-state) to GitHub's `event` action verb.

GitHub's POST /pulls/{n}/reviews endpoint accepts only APPROVE / REQUEST_CHANGES /
COMMENT in the `event` field — *not* the APPROVED / CHANGES_REQUESTED values it
returns when reading a review. Sending the wrong vocabulary triggers a 422 from
real github.com (fake-github is lenient and didn't catch it).
"""

from app.plugins.github.service import _review_event_for_state


def test_approved_maps_to_approve() -> None:
    assert _review_event_for_state("APPROVED") == "APPROVE"


def test_changes_requested_maps_to_request_changes() -> None:
    assert _review_event_for_state("CHANGES_REQUESTED") == "REQUEST_CHANGES"


def test_comment_passes_through() -> None:
    assert _review_event_for_state("COMMENT") == "COMMENT"
