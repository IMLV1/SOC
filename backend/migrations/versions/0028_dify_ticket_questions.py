"""Allow Dify questions with a frozen run policy instead of a legacy KB release."""

from alembic import op

revision = "0028_dify_ticket_questions"
down_revision = "0027_reset_exam_attempt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.analyses DROP CONSTRAINT question_fields")
    op.execute("""ALTER TABLE app.analyses ADD CONSTRAINT question_fields CHECK(
        (kind='question' AND length(btrim(question_text)) BETWEEN 1 AND 2000
          AND question_hash IS NOT NULL AND ticket_id IS NOT NULL
          AND (knowledge_release_id IS NOT NULL OR (mode='real' AND model_id='dify-app')))
        OR (kind='triage' AND question_text IS NULL AND question_hash IS NULL))""")


def downgrade() -> None:
    # Refuse rollback while Dify questions exist rather than deleting history.
    op.execute("ALTER TABLE app.analyses DROP CONSTRAINT question_fields")
    op.execute("""ALTER TABLE app.analyses ADD CONSTRAINT question_fields CHECK(
        (kind='question' AND length(btrim(question_text)) BETWEEN 1 AND 2000
          AND question_hash IS NOT NULL AND ticket_id IS NOT NULL
          AND knowledge_release_id IS NOT NULL)
        OR (kind='triage' AND question_text IS NULL AND question_hash IS NULL))""")
