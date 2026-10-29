"""Remove the fixed tutor USD/day limit while retaining usage records."""

from alembic import op

revision = "0024_remove_tutor_daily_budget"
down_revision = "0023_dify_tutor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.tutor_policy DROP COLUMN daily_usd")
    op.execute("""ALTER TABLE app.tutor_policy
      ADD COLUMN grade_enabled boolean NOT NULL DEFAULT false""")
    op.execute("""ALTER TABLE app.tutor_policy ADD COLUMN grade_call_bound_usd numeric(12,6)
      CHECK(grade_call_bound_usd>0)""")
    op.execute("""ALTER TABLE app.tutor_policy ADD CONSTRAINT tutor_grade_cost_bound
      CHECK(NOT grade_enabled OR grade_call_bound_usd IS NOT NULL)""")
    op.execute("""CREATE TABLE app.written_feedback (
      submission_id uuid PRIMARY KEY REFERENCES app.written_submissions(id),
      owner_user_id uuid NOT NULL REFERENCES app.users(id),
      policy_version integer NOT NULL, workflow_id text NOT NULL,
      corpus_revision text NOT NULL, reserved_usd numeric(12,6) NOT NULL CHECK(reserved_usd>0),
      status text NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued','running','succeeded','needs_review','unavailable','withdrawn')),
      result_json jsonb, error_code text, dispatch_started_at timestamptz,
      reported_tokens bigint CHECK(reported_tokens>=0),
      created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
      CHECK(result_json IS NULL OR status='succeeded')
    )""")
    op.execute("GRANT SELECT,INSERT ON app.written_feedback TO api_runtime")
    op.execute("GRANT SELECT,UPDATE ON app.written_feedback TO worker_runtime")
    op.execute("GRANT SELECT ON app.written_submissions TO worker_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
