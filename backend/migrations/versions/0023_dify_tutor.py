"""Durable lesson tutor with fail-closed release and USD reservation policy."""

from alembic import op

revision = "0023_dify_tutor"
down_revision = "0022_database_training"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.tutor_policy (
 id integer PRIMARY KEY CHECK(id=1), version integer NOT NULL DEFAULT 1,
 enabled boolean NOT NULL DEFAULT false, cost_bound_verified boolean NOT NULL DEFAULT false,
 workflow_id text, corpus_revision text, document_ids jsonb NOT NULL DEFAULT '[]',
 chunk_hashes jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(chunk_hashes)='array'),
 daily_usd numeric(12,6) NOT NULL DEFAULT 0.25 CHECK(daily_usd>0 AND daily_usd<=0.25),
 call_bound_usd numeric(12,6) NOT NULL DEFAULT 0.025 CHECK(call_bound_usd>0),
 CHECK(jsonb_typeof(document_ids)='array'),
 CHECK(NOT enabled OR (cost_bound_verified AND workflow_id IS NOT NULL
   AND corpus_revision IS NOT NULL AND jsonb_array_length(document_ids)>0
   AND jsonb_array_length(chunk_hashes)>0))
);
INSERT INTO app.tutor_policy(id) VALUES(1);
CREATE TABLE app.tutor_questions (
 id uuid PRIMARY KEY, owner_user_id uuid NOT NULL REFERENCES app.users(id),
 lesson_id uuid NOT NULL REFERENCES app.lessons(id),
 question text NOT NULL CHECK(length(question) BETWEEN 1 AND 2000),
 idempotency_key uuid NOT NULL, request_hash text NOT NULL,
 policy_version integer NOT NULL, workflow_id text NOT NULL, corpus_revision text NOT NULL,
 status text NOT NULL DEFAULT 'queued'
 CHECK(status IN ('queued','running','succeeded','needs_review','unavailable','withdrawn')),
 result_json jsonb, error_code text, dispatch_started_at timestamptz,
 budget_day date NOT NULL DEFAULT ((clock_timestamp() AT TIME ZONE 'UTC')::date),
 reserved_usd numeric(12,6) NOT NULL CHECK(reserved_usd>0),
 usage_status text NOT NULL DEFAULT 'reserved'
 CHECK(usage_status IN ('reserved','unknown','reconciled','released')),
 reported_tokens bigint CHECK(reported_tokens>=0),
 created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '30 days',
 UNIQUE(owner_user_id,idempotency_key), CHECK(result_json IS NULL OR status='succeeded')
);
CREATE INDEX tutor_owner_history ON app.tutor_questions(owner_user_id,created_at DESC,id);
GRANT SELECT ON app.tutor_policy TO api_runtime,worker_runtime;
GRANT SELECT,INSERT ON app.tutor_questions TO api_runtime;
GRANT SELECT,UPDATE ON app.tutor_questions TO worker_runtime;
GRANT SELECT(owner_user_id,status) ON app.exam_attempts TO worker_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
