"""Isolated exam cases, immutable submissions, grading history, and level unlocks."""

from alembic import op

revision = "0020_exam_attempts"
down_revision = "0019_learning_path"
branch_labels = None
depends_on = None

DDL = """
ALTER TABLE app.runs ADD COLUMN mode text NOT NULL DEFAULT 'training'
 CHECK (mode IN ('training','exam'));
ALTER TABLE app.scenarios DROP CONSTRAINT scenarios_purpose_check;
ALTER TABLE app.scenarios ADD CONSTRAINT scenarios_purpose_check
 CHECK (purpose IN ('training','exam'));
ALTER TABLE app.scenarios DROP CONSTRAINT scenarios_stable_key_check;
ALTER TABLE app.scenarios ADD CONSTRAINT scenarios_stable_key_check
 CHECK (stable_key ~ '^(S0[1-5]|E[0-9]{2})$');
GRANT SELECT(stable_key,purpose) ON app.scenarios TO api_runtime;

CREATE TABLE app.exam_cases (
 id uuid PRIMARY KEY,
 scenario_id uuid NOT NULL UNIQUE REFERENCES app.scenarios(id),
 level_id uuid NOT NULL REFERENCES app.learning_levels(id),
 stable_key text NOT NULL,
 version integer NOT NULL CHECK(version>0),
 duration_ms integer NOT NULL CHECK(duration_ms BETWEEN 1000 AND 3600000),
 enabled boolean NOT NULL DEFAULT false,
 seed_hash text NOT NULL CHECK(seed_hash ~ '^[0-9a-f]{64}$'),
 UNIQUE(stable_key,version), UNIQUE(id,level_id)
);
CREATE TABLE private.exam_case_truths (
 case_id uuid NOT NULL REFERENCES app.exam_cases(id),
 version integer NOT NULL CHECK(version>0),
 expected_evidence_keys jsonb NOT NULL CHECK(jsonb_typeof(expected_evidence_keys)='array'),
 expected_severity text NOT NULL CHECK(expected_severity IN ('low','medium','high','critical')),
 expected_disposition text NOT NULL CHECK(expected_disposition IN
   ('true_positive','false_positive','undetermined')),
 criterion_guidance jsonb NOT NULL CHECK(jsonb_typeof(criterion_guidance)='object'),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(case_id,version)
);
CREATE TABLE app.exam_attempts (
 id uuid PRIMARY KEY,
 owner_user_id uuid NOT NULL REFERENCES app.users(id),
 level_id uuid NOT NULL REFERENCES app.learning_levels(id),
 case_id uuid NOT NULL,
 run_id uuid NOT NULL UNIQUE REFERENCES app.runs(id),
 status text NOT NULL CHECK(status IN
   ('in_progress','submitted','needs_review','passed','failed','expired')),
 rubric_version text NOT NULL,
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 started_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 submitted_at timestamptz,
 finalized_at timestamptz,
 FOREIGN KEY(case_id,level_id) REFERENCES app.exam_cases(id,level_id),
 CHECK(expires_at>started_at),
 CHECK((status IN ('submitted','needs_review','passed','failed'))=(submitted_at IS NOT NULL))
);
CREATE INDEX exam_attempt_owner_history
 ON app.exam_attempts(owner_user_id,level_id,started_at DESC);
CREATE UNIQUE INDEX one_active_exam_per_owner ON app.exam_attempts(owner_user_id)
 WHERE status IN ('in_progress','submitted','needs_review');
CREATE TABLE app.exam_answers (
 attempt_id uuid PRIMARY KEY REFERENCES app.exam_attempts(id),
 evidence_event_ids jsonb NOT NULL CHECK(jsonb_typeof(evidence_event_ids)='array'),
 severity text NOT NULL CHECK(severity IN ('low','medium','high','critical')),
 disposition text NOT NULL CHECK(disposition IN ('true_positive','false_positive','undetermined')),
 reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 2000),
 release_cutoff bigint NOT NULL CHECK(release_cutoff>=0),
 assessment_cutoff timestamptz NOT NULL,
 dataset_hash text NOT NULL CHECK(dataset_hash ~ '^[0-9a-f]{64}$'),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 frozen_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.grading_revisions (
 id uuid PRIMARY KEY,
 attempt_id uuid NOT NULL REFERENCES app.exam_attempts(id),
 revision integer NOT NULL CHECK(revision>0),
 source text NOT NULL CHECK(source IN ('deterministic','instructor')),
 rubric_version text NOT NULL,
 status text NOT NULL CHECK(status IN ('passed','failed','needs_review')),
 score integer CHECK(score BETWEEN 0 AND 8),
 criteria_json jsonb NOT NULL CHECK(jsonb_typeof(criteria_json)='array'),
 reviewer_user_id uuid REFERENCES app.users(id),
 model_id text,
 knowledge_release_id uuid,
 reason text,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(attempt_id,revision),
 CHECK((source='instructor')=(reviewer_user_id IS NOT NULL))
);
CREATE TABLE app.level_unlocks (
 user_id uuid NOT NULL REFERENCES app.users(id),
 level_id uuid NOT NULL REFERENCES app.learning_levels(id),
 earned_from_revision_id uuid NOT NULL REFERENCES app.grading_revisions(id),
 unlocked_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,level_id)
);
GRANT SELECT,INSERT,UPDATE ON app.runs TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.exam_attempts TO api_runtime;
GRANT SELECT,INSERT ON app.exam_answers,app.grading_revisions,app.level_unlocks TO api_runtime;
GRANT SELECT ON app.exam_cases TO api_runtime;
GRANT SELECT ON app.exam_cases TO evaluator_runtime;
GRANT USAGE ON SCHEMA private TO api_runtime;
GRANT SELECT,INSERT ON private.exam_case_truths TO migration_owner;
GRANT SELECT ON private.exam_case_truths TO evaluator_runtime;

"""

FUNCTIONS = (
    """CREATE FUNCTION app.exam_fixture_hash(p_scenario uuid) RETURNS text
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,pg_temp
    AS $$ SELECT s.fixture_hash FROM app.scenarios s
          JOIN app.exam_cases c ON c.scenario_id=s.id
          WHERE s.id=p_scenario AND s.enabled AND s.purpose='exam' AND c.enabled $$""",
    """CREATE FUNCTION private.instructor_exam_truth(p_actor uuid,p_attempt uuid) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=app,private,pg_temp AS $$
    DECLARE truth jsonb;
    BEGIN
      SELECT jsonb_build_object(
        'expectedEvidenceKeys',t.expected_evidence_keys,
        'expectedSeverity',t.expected_severity,
        'expectedDisposition',t.expected_disposition,
        'criterionGuidance',t.criterion_guidance)
      INTO truth
      FROM app.exam_attempts a
      JOIN app.users u ON u.id=p_actor AND u.role='instructor' AND u.status='active'
      JOIN app.instructor_assignments ia ON ia.instructor_user_id=p_actor
        AND ia.analyst_user_id=a.owner_user_id
      JOIN app.exam_cases c ON c.id=a.case_id
      JOIN app.scenarios s ON s.id=c.scenario_id
      JOIN private.exam_case_truths t ON t.case_id=c.id AND t.version=s.version
      WHERE a.id=p_attempt AND a.status IN ('submitted','needs_review','passed','failed');
      IF truth IS NULL THEN RETURN NULL; END IF;
      INSERT INTO app.audit_logs(id,actor_user_id,actor_role,action,entity_type,entity_id,reason)
      VALUES(gen_random_uuid(),p_actor,'instructor','exam.truth.read','exam_attempt',p_attempt,
             'Authorized after submission');
      RETURN truth;
    END $$""",
    """CREATE FUNCTION app.exam_truth_version(p_scenario uuid) RETURNS integer
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,private,pg_temp
    AS $$ SELECT coalesce(max(t.version),1)::integer FROM private.exam_case_truths t
          JOIN app.exam_cases c ON c.id=t.case_id
          WHERE c.scenario_id=p_scenario AND c.enabled $$""",
)


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)
    for statement in FUNCTIONS:
        op.execute(statement)
    op.execute("REVOKE ALL ON FUNCTION app.exam_fixture_hash(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.exam_fixture_hash(uuid) TO api_runtime")
    op.execute("REVOKE ALL ON FUNCTION private.instructor_exam_truth(uuid,uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION private.instructor_exam_truth(uuid,uuid) TO api_runtime")
    op.execute("REVOKE ALL ON FUNCTION app.exam_truth_version(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.exam_truth_version(uuid) TO api_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration")
