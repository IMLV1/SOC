"""Prevent runtime workers from rewriting released evidence snapshots."""

from alembic import op

revision = "0008_immutable_released_events"
down_revision = "0007_mock_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Runner workers append released events. Analysis and detection snapshots
    # refer to those rows, so runtime roles must not be able to rewrite them.
    op.execute("REVOKE UPDATE, DELETE ON app.events FROM worker_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
