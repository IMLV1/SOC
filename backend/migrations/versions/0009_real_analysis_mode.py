"""Allow runs and analyses to pin the explicitly configured real provider."""

from alembic import op

revision = "0009_real_analysis_mode"
down_revision = "0008_immutable_released_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.runs DROP CONSTRAINT runs_analysis_mode_check")
    op.execute(
        "ALTER TABLE app.runs ADD CONSTRAINT runs_analysis_mode_check "
        "CHECK (analysis_mode IN ('mock','real'))"
    )
    op.execute("ALTER TABLE app.analyses DROP CONSTRAINT analyses_mode_check")
    op.execute(
        "ALTER TABLE app.analyses ADD CONSTRAINT analyses_mode_check CHECK (mode IN ('mock','real'))"
    )


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
