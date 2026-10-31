"""Allow an audited reset of a failed AI grading attempt without deleting it."""

from alembic import op

revision = "0027_reset_exam_attempt"
down_revision = "0026_exam_ai_grading"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.exam_attempts ADD COLUMN reset_at timestamptz")
    op.execute("ALTER TABLE app.exam_attempts ADD COLUMN reset_reason text")
    op.execute(
        """DO $$ DECLARE c record; BEGIN
        FOR c IN SELECT conname FROM pg_constraint
          WHERE conrelid='app.exam_attempts'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%status%in_progress%'
        LOOP EXECUTE format('ALTER TABLE app.exam_attempts DROP CONSTRAINT %I', c.conname);
        END LOOP;
        FOR c IN SELECT conname FROM pg_constraint
          WHERE conrelid='app.exam_attempts'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%submitted_at IS NOT NULL%'
        LOOP EXECUTE format('ALTER TABLE app.exam_attempts DROP CONSTRAINT %I', c.conname);
        END LOOP;
        END $$"""
    )
    op.execute(
        """ALTER TABLE app.exam_attempts ADD CONSTRAINT exam_attempts_status_check
        CHECK(status IN ('in_progress','submitted','needs_review','passed','failed','expired','reset'))"""
    )
    op.execute(
        """ALTER TABLE app.exam_attempts ADD CONSTRAINT exam_attempts_submission_timestamp_check
        CHECK((status IN ('submitted','needs_review','passed','failed','reset'))
          = (submitted_at IS NOT NULL))"""
    )
    op.execute(
        """ALTER TABLE app.exam_attempts ADD CONSTRAINT exam_attempts_reset_fields_check
        CHECK((status='reset') = (reset_at IS NOT NULL AND reset_reason IS NOT NULL))"""
    )
    op.execute(
        """CREATE FUNCTION private.reset_exam_attempt(p_owner uuid,p_attempt uuid)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=app,private,pg_temp AS $$
        DECLARE a app.exam_attempts%ROWTYPE; g app.exam_ai_grades%ROWTYPE;
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtextextended(p_owner::text,73102006));
          SELECT * INTO a FROM app.exam_attempts
            WHERE id=p_attempt AND owner_user_id=p_owner FOR UPDATE;
          IF NOT FOUND OR a.status <> 'needs_review' THEN RETURN false; END IF;
          SELECT * INTO g FROM app.exam_ai_grades WHERE attempt_id=p_attempt FOR UPDATE;
          IF NOT FOUND OR g.status <> 'needs_review'
            OR g.error_code <> 'DIFY_CONFIGURATION_INVALID' THEN RETURN false; END IF;
          IF EXISTS (SELECT 1 FROM app.jobs WHERE type='exam_grade'
            AND payload->>'attempt_id'=p_attempt::text AND status IN ('queued','running'))
            OR EXISTS (SELECT 1 FROM app.grading_revisions WHERE attempt_id=p_attempt)
            OR EXISTS (SELECT 1 FROM app.level_unlocks u JOIN app.grading_revisions r
              ON r.id=u.earned_from_revision_id WHERE r.attempt_id=p_attempt)
            THEN RETURN false; END IF;
          UPDATE app.exam_attempts SET status='reset',reset_at=clock_timestamp(),
            reset_reason='learner_requested_after_dify_configuration_failure',version=version+1
            WHERE id=p_attempt;
          INSERT INTO app.audit_logs
            (id,actor_user_id,actor_role,action,entity_type,entity_id,before_json,after_json,reason)
          VALUES (gen_random_uuid(),p_owner,'analyst','exam.attempt.reset','exam_attempt',p_attempt,
            jsonb_build_object('status','needs_review','grade_error',g.error_code),
            jsonb_build_object('status','reset'),
            'Learner requested a new test after Dify configuration failure; frozen answer and usage record retained');
          RETURN true;
        END $$"""
    )
    op.execute("REVOKE ALL ON FUNCTION private.reset_exam_attempt(uuid,uuid) FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA private TO retention_runtime")
    op.execute("GRANT EXECUTE ON FUNCTION private.reset_exam_attempt(uuid,uuid) TO retention_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
