"""Shared USD accounting for separately reviewed investigation releases."""

from alembic import op

revision = "0024_investigation_budget"
down_revision = "0023_dify_tutor"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.investigation_calls (
 analysis_id uuid PRIMARY KEY REFERENCES app.analyses(id),
 release_hash text NOT NULL CHECK(length(release_hash)=64),
 reserved_usd numeric(12,6) NOT NULL CHECK(reserved_usd>0 AND reserved_usd<=0.25),
 budget_day date NOT NULL DEFAULT ((clock_timestamp() AT TIME ZONE 'UTC')::date),
 usage_status text NOT NULL DEFAULT 'unknown'
 CHECK(usage_status IN ('unknown','reconciled')),
 reported_tokens bigint CHECK(reported_tokens>=0),
 error_code text, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
GRANT SELECT ON app.investigation_calls TO api_runtime,evaluator_runtime;
GRANT SELECT,INSERT ON app.investigation_calls TO worker_runtime;
GRANT UPDATE(usage_status,reported_tokens,error_code) ON app.investigation_calls TO worker_runtime;
CREATE INDEX investigation_release_drift ON app.investigation_calls(release_hash)
 WHERE error_code='DIFY_WORKFLOW_VERSION_MISMATCH';
GRANT SELECT ON app.tutor_questions,app.tutor_policy TO worker_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
