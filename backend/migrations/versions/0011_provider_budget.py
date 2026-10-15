"""Approved free-tier provider call budgets and auditable usage holds."""

from alembic import op

revision = "0011_provider_budget"
down_revision = "0010_evaluation_experiments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE app.provider_policy (
        id integer PRIMARY KEY CHECK(id=1),version text NOT NULL,
        daily_requests integer NOT NULL CHECK(daily_requests>0),
        daily_tokens bigint NOT NULL CHECK(daily_tokens>0),
        rpm integer NOT NULL CHECK(rpm>0),cooldown_until timestamptz,
        input_usd_per_million numeric NOT NULL CHECK(input_usd_per_million=0),
        output_usd_per_million numeric NOT NULL CHECK(output_usd_per_million=0)
    )""")
    op.execute("""INSERT INTO app.provider_policy VALUES
        (1,'gemini-free-2026-10-15-v1',100,200000,5,NULL,0,0)""")
    op.execute("""CREATE TABLE app.provider_calls (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        analysis_id uuid UNIQUE REFERENCES app.analyses(id),
        experiment_arm_id uuid UNIQUE REFERENCES app.experiment_arms(id),
        component text NOT NULL CHECK(component='generation'),
        policy_version text NOT NULL,model_id text NOT NULL,
        dispatched_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        reserved_tokens bigint NOT NULL CHECK(reserved_tokens>0),
        actual_tokens bigint CHECK(actual_tokens>=0),
        status text NOT NULL CHECK(status IN ('unknown','consumed','released')),
        reconciled_at timestamptz,reconciliation_reason text,
        CHECK((reconciled_at IS NULL)=(reconciliation_reason IS NULL)),
        CHECK((analysis_id IS NULL)<>(experiment_arm_id IS NULL))
    )""")
    op.execute("CREATE INDEX provider_calls_dispatched ON app.provider_calls(dispatched_at)")
    op.execute("GRANT SELECT ON app.provider_policy,app.provider_calls TO worker_runtime")
    op.execute("GRANT UPDATE(cooldown_until) ON app.provider_policy TO worker_runtime")
    op.execute("GRANT INSERT,UPDATE ON app.provider_calls TO worker_runtime")
    op.execute("ALTER TABLE app.quota_reservations ALTER COLUMN analysis_id DROP NOT NULL")
    op.execute("""ALTER TABLE app.quota_reservations ADD COLUMN experiment_arm_id uuid
        REFERENCES app.experiment_arms(id), ADD UNIQUE(experiment_arm_id,ledger_id),
        ADD CHECK((analysis_id IS NULL)<>(experiment_arm_id IS NULL))""")
    op.execute("""GRANT SELECT ON app.experiment_batches,app.experiment_arms,
        app.evaluations,app.instructor_assignments TO worker_runtime""")
    op.execute("GRANT UPDATE ON app.experiment_arms TO worker_runtime")
    op.execute("GRANT UPDATE(status) ON app.experiment_batches TO worker_runtime")
    op.execute("GRANT SELECT(id,status,role) ON app.users TO worker_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
