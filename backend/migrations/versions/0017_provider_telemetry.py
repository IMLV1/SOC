"""Track model token counting separately from generated token usage."""

from alembic import op

revision = "0017_provider_telemetry"
down_revision = "0016_rag_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE app.provider_calls
      DROP CONSTRAINT provider_calls_component_check,
      ADD CHECK(component IN ('generation','query_embedding','document_embedding','token_count')),
      ADD COLUMN telemetry_json jsonb NOT NULL DEFAULT '{}'::jsonb,
      ADD CHECK(jsonb_typeof(telemetry_json)='object')""")
    op.execute("""ALTER TABLE app.retrievals ADD COLUMN latency_ms integer
      CHECK(latency_ms>=0)""")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
