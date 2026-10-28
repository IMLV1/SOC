"""Database-backed practice, immutable feedback, and written exam submissions."""

from alembic import op

revision = "0022_database_training"
down_revision = "0021_supabase_auth"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.demo_events (
 id uuid PRIMARY KEY, ordinal integer NOT NULL UNIQUE, content_json jsonb NOT NULL,
 CHECK(jsonb_typeof(content_json)='object')
);
GRANT SELECT ON app.demo_events TO api_runtime;
CREATE TABLE app.practice_cases (
 id uuid PRIMARY KEY, stable_key text NOT NULL UNIQUE,
 level_id uuid NOT NULL REFERENCES app.learning_levels(id), category text NOT NULL,
 title text NOT NULL, version integer NOT NULL CHECK(version>0),
 content_json jsonb NOT NULL CHECK(jsonb_typeof(content_json)='object'),
 content_hash text NOT NULL CHECK(length(content_hash)=64),
 published_at timestamptz NOT NULL DEFAULT now(), enabled boolean NOT NULL DEFAULT true,
 UNIQUE(id,version)
);
CREATE TABLE private.practice_truths (
 case_id uuid PRIMARY KEY REFERENCES app.practice_cases(id),
 severity text NOT NULL CHECK(severity IN ('low','medium','high','critical')),
 disposition text NOT NULL CHECK(disposition IN ('true_positive','false_positive','undetermined')),
 evidence_ids jsonb NOT NULL CHECK(jsonb_typeof(evidence_ids)='array'),
 explanation text NOT NULL, limitation text NOT NULL
);
CREATE TABLE app.practice_drafts (
 owner_user_id uuid NOT NULL REFERENCES app.users(id),
 case_id uuid NOT NULL REFERENCES app.practice_cases(id),
 answer_json jsonb NOT NULL CHECK(jsonb_typeof(answer_json)='object'),
 version integer NOT NULL CHECK(version>0), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(owner_user_id,case_id)
);
CREATE TABLE app.practice_answers (
 id uuid PRIMARY KEY, owner_user_id uuid NOT NULL REFERENCES app.users(id),
 case_id uuid NOT NULL, case_version integer NOT NULL,
 idempotency_key uuid NOT NULL, request_hash text NOT NULL CHECK(length(request_hash)=64),
 answer_json jsonb NOT NULL CHECK(jsonb_typeof(answer_json)='object'),
 evidence_snapshot jsonb NOT NULL CHECK(jsonb_typeof(evidence_snapshot)='object'),
 feedback_json jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(case_id,case_version) REFERENCES app.practice_cases(id,version),
 UNIQUE(owner_user_id,case_id,idempotency_key)
);
CREATE INDEX practice_answer_history ON app.practice_answers(owner_user_id,case_id,created_at DESC);
CREATE TABLE app.written_questions (
 id uuid PRIMARY KEY, level_id uuid NOT NULL REFERENCES app.learning_levels(id),
 ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 10), version integer NOT NULL DEFAULT 1,
 prompt text NOT NULL, category text NOT NULL,
 UNIQUE(level_id,ordinal), UNIQUE(id,version)
);
CREATE TABLE app.written_submissions (
 id uuid PRIMARY KEY, owner_user_id uuid NOT NULL REFERENCES app.users(id),
 level_id uuid NOT NULL REFERENCES app.learning_levels(id),
 idempotency_key uuid NOT NULL, request_hash text NOT NULL CHECK(length(request_hash)=64),
 answers_json jsonb NOT NULL CHECK(jsonb_typeof(answers_json)='array'),
 question_snapshot jsonb NOT NULL CHECK(jsonb_typeof(question_snapshot)='array'),
 status text NOT NULL DEFAULT 'needs_review' CHECK(status='needs_review'),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_user_id,level_id,idempotency_key)
);
GRANT SELECT ON app.practice_cases,app.written_questions TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.practice_drafts TO api_runtime;
GRANT SELECT,INSERT ON app.practice_answers,app.written_submissions TO api_runtime;
GRANT SELECT ON app.practice_answers,app.written_submissions TO evaluator_runtime;
"""

REVIEW = """CREATE FUNCTION private.review_practice(p_actor uuid,p_answer uuid) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
 DECLARE a app.practice_answers; t private.practice_truths; result jsonb;
 BEGIN
   SELECT * INTO a FROM app.practice_answers WHERE id=p_answer AND owner_user_id=p_actor;
   IF a.id IS NULL THEN RETURN NULL; END IF;
   IF a.feedback_json IS NOT NULL THEN RETURN a.feedback_json; END IF;
   SELECT * INTO STRICT t FROM private.practice_truths WHERE case_id=a.case_id;
   result := jsonb_build_object(
     'mode','deterministic',
     'classification_correct', a.answer_json->>'severity'=t.severity AND
       a.answer_json->>'disposition'=t.disposition,
     'evidence_correct', (a.answer_json->'evidence_ids') @> t.evidence_ids AND
       t.evidence_ids @> (a.answer_json->'evidence_ids'),
     'expected_severity',t.severity,'expected_disposition',t.disposition,
     'explanation',t.explanation,'limitation',t.limitation,
     'reason_review_status','unavailable',
     'reason_review_message','บันทึกเหตุผลแล้ว ยังไม่ประเมินความหมายของข้อความจนกว่าจะเชื่อม Dify',
     'is_exam_result',false);
   UPDATE app.practice_answers SET feedback_json=result WHERE id=a.id;
   RETURN result;
 END $$"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)
    op.execute(REVIEW)
    op.execute("REVOKE ALL ON FUNCTION private.review_practice(uuid,uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION private.review_practice(uuid,uuid) TO api_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a forward migration")
