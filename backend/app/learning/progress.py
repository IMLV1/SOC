from collections.abc import Sequence

from app.auth.service import AuthError


def apply_progress(
    completed_steps: Sequence[str],
    *,
    completed: bool,
    current_version: int,
    expected_version: int,
    step_id: str | None,
    allowed_steps: Sequence[str],
) -> tuple[list[str], bool]:
    """Validate a versioned step or completion request; return new steps and changed flag."""
    steps = list(completed_steps)
    if step_id is not None and step_id not in allowed_steps:
        raise AuthError(404, "NOT_FOUND")
    if expected_version != current_version:
        if (step_id is None and completed) or (step_id is not None and step_id in steps):
            return steps, False
        raise AuthError(409, "VERSION_CONFLICT")
    if step_id is not None:
        expected = allowed_steps[len(steps)] if len(steps) < len(allowed_steps) else None
        if step_id in steps:
            return steps, False
        if step_id != expected:
            raise AuthError(409, "STEP_ORDER_INVALID")
        steps.append(step_id)
        return steps, True
    if len(steps) != len(allowed_steps):
        raise AuthError(409, "LESSON_INCOMPLETE")
    return steps, not completed
