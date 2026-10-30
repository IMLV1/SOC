"""Add opt-in Dify modes for practice questions and run analysis."""

from alembic import op

revision = "0025_dify_practice_and_analysis"
down_revision = "0024_remove_tutor_daily_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.tutor_policy ADD COLUMN practice_enabled boolean NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE app.tutor_policy ADD COLUMN analysis_enabled boolean NOT NULL DEFAULT false"
    )
    op.execute("""ALTER TABLE app.tutor_policy ADD COLUMN practice_call_bound_usd numeric(12,6)
      CHECK(practice_call_bound_usd>0)""")
    op.execute("""ALTER TABLE app.tutor_policy ADD COLUMN analysis_call_bound_usd numeric(12,6)
      CHECK(analysis_call_bound_usd>0)""")
    op.execute("""ALTER TABLE app.tutor_policy ADD CONSTRAINT tutor_practice_cost_bound
      CHECK(NOT practice_enabled OR practice_call_bound_usd IS NOT NULL)""")
    op.execute("""ALTER TABLE app.tutor_policy ADD CONSTRAINT tutor_analysis_cost_bound
      CHECK(NOT analysis_enabled OR analysis_call_bound_usd IS NOT NULL)""")
    op.execute("""CREATE TABLE app.practice_ai_questions (
      id uuid PRIMARY KEY,
      owner_user_id uuid NOT NULL REFERENCES app.users(id),
      case_id uuid NOT NULL REFERENCES app.practice_cases(id),
      answer_id uuid NOT NULL REFERENCES app.practice_answers(id),
      question text NOT NULL CHECK(length(question) BETWEEN 1 AND 2000),
      idempotency_key uuid NOT NULL, request_hash text NOT NULL,
      policy_version integer NOT NULL, workflow_id text NOT NULL,
      corpus_revision text NOT NULL,
      reserved_usd numeric(12,6) NOT NULL CHECK(reserved_usd>0),
      status text NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued','running','succeeded','needs_review','unavailable','withdrawn')),
      result_json jsonb, error_code text, dispatch_started_at timestamptz,
      usage_status text NOT NULL DEFAULT 'reserved'
        CHECK(usage_status IN ('reserved','unknown','reconciled','released')),
      reported_tokens bigint CHECK(reported_tokens>=0),
      created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
      expires_at timestamptz NOT NULL DEFAULT now()+interval '30 days',
      UNIQUE(owner_user_id,idempotency_key),
      CHECK(result_json IS NULL OR status='succeeded')
    )""")
    op.execute("""CREATE INDEX practice_ai_owner_history
      ON app.practice_ai_questions(owner_user_id,case_id,created_at DESC,id)""")
    op.execute("GRANT SELECT,INSERT ON app.practice_ai_questions TO api_runtime")
    op.execute("GRANT SELECT,UPDATE ON app.practice_ai_questions TO worker_runtime")
    op.execute("GRANT SELECT ON app.practice_answers TO worker_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
