"""Queue isolated, opt-in AI grading after a frozen exam submission."""

from alembic import op

revision = "0026_exam_ai_grading"
down_revision = "0025_dify_practice_and_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.tutor_policy ADD COLUMN exam_grade_enabled boolean NOT NULL DEFAULT false"
    )
    op.execute("""ALTER TABLE app.tutor_policy ADD COLUMN exam_grade_call_bound_usd numeric(12,6)
      CHECK(exam_grade_call_bound_usd>0)""")
    op.execute("""ALTER TABLE app.tutor_policy ADD CONSTRAINT tutor_exam_grade_cost_bound
      CHECK(NOT exam_grade_enabled OR exam_grade_call_bound_usd IS NOT NULL)""")
    op.execute(
        """ALTER TABLE app.grading_revisions DROP CONSTRAINT grading_revisions_source_check"""
    )
    op.execute("""ALTER TABLE app.grading_revisions ADD CONSTRAINT grading_revisions_source_check
      CHECK(source IN ('deterministic','instructor','ai'))""")
    op.execute("""ALTER TABLE app.grading_revisions DROP CONSTRAINT grading_revisions_check""")
    op.execute("""ALTER TABLE app.grading_revisions ADD CONSTRAINT grading_revisions_check
      CHECK((source='instructor')=(reviewer_user_id IS NOT NULL))""")
    op.execute("""CREATE TABLE app.exam_ai_grades (
      attempt_id uuid PRIMARY KEY REFERENCES app.exam_attempts(id),
      owner_user_id uuid NOT NULL REFERENCES app.users(id),
      policy_version integer NOT NULL, workflow_id text NOT NULL,
      corpus_revision text NOT NULL,
      reserved_usd numeric(12,6) NOT NULL CHECK(reserved_usd>0),
      status text NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued','running','succeeded','needs_review','unavailable','withdrawn')),
      error_code text, dispatch_started_at timestamptz,
      usage_status text NOT NULL DEFAULT 'reserved'
        CHECK(usage_status IN ('reserved','unknown','reconciled','released')),
      reported_tokens bigint CHECK(reported_tokens>=0),
      created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
    )""")
    op.execute("GRANT SELECT,INSERT ON app.exam_ai_grades TO api_runtime")
    op.execute("GRANT SELECT,UPDATE ON app.exam_ai_grades TO evaluator_runtime")
    op.execute(
        """GRANT SELECT ON app.tutor_policy,app.exam_attempts,app.exam_answers,
        app.exam_cases,app.learning_levels,app.grading_revisions,app.level_unlocks
        TO evaluator_runtime"""
    )
    op.execute("GRANT UPDATE ON app.exam_attempts TO evaluator_runtime")
    op.execute("GRANT INSERT ON app.grading_revisions,app.level_unlocks TO evaluator_runtime")
    op.execute("GRANT SELECT ON private.exam_case_truths TO evaluator_runtime")
    op.execute("GRANT SELECT ON app.quota_ledgers TO evaluator_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
