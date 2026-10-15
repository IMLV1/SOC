"""Frozen training evaluations, instructor review, and experiment records."""

# ruff: noqa: E501

from alembic import op

revision = "0010_evaluation_experiments"
down_revision = "0009_real_analysis_mode"
branch_labels = None
depends_on = None

DDL = """
ALTER TABLE app.run_versions ADD COLUMN ground_truth_versions jsonb NOT NULL DEFAULT '{}'::jsonb;
UPDATE app.run_versions rv SET ground_truth_versions=coalesce((
 SELECT jsonb_object_agg(x.scenario_id::text,x.truth_version) FROM (
  SELECT i.scenario_id,coalesce(max(g.truth_version),1) AS truth_version
  FROM app.scenario_instances i LEFT JOIN private.ground_truth g ON g.scenario_id=i.scenario_id
  WHERE i.run_id=rv.run_id GROUP BY i.scenario_id
 ) x
),'{}'::jsonb);
CREATE TABLE app.evaluations (
 id uuid PRIMARY KEY,run_id uuid NOT NULL REFERENCES app.runs(id),revision integer NOT NULL CHECK(revision>0),
 status text NOT NULL CHECK(status IN ('pending','completed','failed')),
 release_cutoff bigint NOT NULL,assessment_cutoff timestamptz NOT NULL,ground_truth_version integer NOT NULL,
 dataset_hash text NOT NULL CHECK(dataset_hash ~ '^[0-9a-f]{64}$'),truncated boolean NOT NULL,
 snapshot_json jsonb NOT NULL CHECK(jsonb_typeof(snapshot_json)='object'),metrics_json jsonb,
 versions_json jsonb NOT NULL CHECK(jsonb_typeof(versions_json)='object'),created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz, UNIQUE(run_id,revision),UNIQUE(run_id,id),
 CHECK((status='completed')=(completed_at IS NOT NULL))
);
CREATE TABLE app.evaluation_items (
 id uuid PRIMARY KEY,run_id uuid NOT NULL,evaluation_id uuid NOT NULL,scenario_instance_id uuid NOT NULL,
 incident_key text NOT NULL,ground_truth_label boolean NOT NULL,evidence_complete boolean NOT NULL,
 correct boolean,ticket_deleted boolean NOT NULL,snapshot_json jsonb NOT NULL CHECK(jsonb_typeof(snapshot_json)='object'),
 UNIQUE(evaluation_id,scenario_instance_id,incident_key),
 FOREIGN KEY(run_id,evaluation_id) REFERENCES app.evaluations(run_id,id),
 FOREIGN KEY(run_id,scenario_instance_id) REFERENCES app.scenario_instances(run_id,id)
);
CREATE TABLE private.evaluation_truth (
 id uuid PRIMARY KEY,run_id uuid NOT NULL,evaluation_id uuid NOT NULL,scenario_instance_id uuid NOT NULL,
 incident_key text NOT NULL,truth_version integer NOT NULL,threat_label boolean NOT NULL,expected_evidence_keys jsonb NOT NULL,
 explanation text NOT NULL,UNIQUE(evaluation_id,scenario_instance_id,incident_key),
 FOREIGN KEY(run_id,evaluation_id) REFERENCES app.evaluations(run_id,id),
 FOREIGN KEY(run_id,scenario_instance_id) REFERENCES app.scenario_instances(run_id,id)
);
CREATE TABLE app.instructor_run_comments (
 id uuid PRIMARY KEY,instructor_user_id uuid NOT NULL REFERENCES app.users(id),analyst_user_id uuid NOT NULL REFERENCES app.users(id),
 run_id uuid NOT NULL REFERENCES app.runs(id),body varchar(2000) NOT NULL CHECK(length(btrim(body)) BETWEEN 1 AND 2000),
 created_at timestamptz NOT NULL DEFAULT now(),deleted_at timestamptz
);
CREATE TABLE app.experiment_batches (
 id uuid PRIMARY KEY,dataset_run_id uuid NOT NULL REFERENCES app.runs(id),requested_by uuid NOT NULL REFERENCES app.users(id),
 dataset_hash text NOT NULL CHECK(dataset_hash ~ '^[0-9a-f]{64}$'),config_versions jsonb NOT NULL,
 truncated boolean NOT NULL,status text NOT NULL CHECK(status IN ('running','completed','failed')),created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.experiment_arms (
 id uuid PRIMARY KEY,batch_id uuid NOT NULL REFERENCES app.experiment_batches(id),mode text NOT NULL CHECK(mode IN ('A','B','C')),
 status text NOT NULL CHECK(status IN ('pending','completed','unavailable','failed')),
 config_snapshot jsonb NOT NULL,outputs_json jsonb,metrics_json jsonb,error_code text,
 UNIQUE(batch_id,mode),CHECK((mode='C' AND status='unavailable') OR mode IN ('A','B') OR mode='C')
);
CREATE TRIGGER evaluation_immutable BEFORE UPDATE OR DELETE ON app.evaluations
 FOR EACH ROW EXECUTE FUNCTION app.guard_evaluation_immutable();
CREATE TRIGGER evaluation_items_immutable BEFORE UPDATE OR DELETE ON app.evaluation_items
 FOR EACH ROW EXECUTE FUNCTION app.guard_evaluation_item_immutable();
CREATE TRIGGER evaluation_truth_immutable BEFORE UPDATE OR DELETE ON private.evaluation_truth
 FOR EACH ROW EXECUTE FUNCTION app.guard_evaluation_item_immutable();
GRANT SELECT ON app.evaluations TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.instructor_run_comments,app.experiment_batches,app.experiment_arms TO api_runtime;
GRANT SELECT ON app.evaluations,app.instructor_run_comments TO api_runtime;
GRANT SELECT ON app.runs,app.events,app.tickets,app.ticket_events,app.ticket_alerts,
 app.detections,app.detection_evidence,app.alerts,app.assessments,app.analysis_attempts TO evaluator_runtime;
GRANT SELECT ON app.run_versions TO evaluator_runtime;
GRANT SELECT,INSERT ON app.evaluations,app.evaluation_items TO evaluator_runtime;
GRANT SELECT,INSERT ON private.evaluation_truth TO evaluator_runtime;
GRANT SELECT ON app.runs,app.events,app.tickets,app.ticket_events,app.assessments,app.scenario_instances,app.scenarios TO evaluator_runtime;
GRANT SELECT,UPDATE ON app.jobs TO evaluator_runtime;
GRANT UPDATE(status,completed_at,version) ON app.runs TO evaluator_runtime;
GRANT SELECT ON app.run_completions,app.detection_evidence,app.ticket_events,app.scenarios TO evaluator_runtime;
GRANT SELECT ON app.analyses,app.analysis_evidence,app.analysis_attempts TO evaluator_runtime;
GRANT USAGE ON SCHEMA private TO api_runtime;
"""


def upgrade() -> None:
    op.execute("""CREATE FUNCTION app.guard_evaluation_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR OLD.snapshot_json IS DISTINCT FROM NEW.snapshot_json OR
         OLD.run_id IS DISTINCT FROM NEW.run_id OR OLD.revision IS DISTINCT FROM NEW.revision OR
         OLD.release_cutoff IS DISTINCT FROM NEW.release_cutoff OR
         OLD.assessment_cutoff IS DISTINCT FROM NEW.assessment_cutoff OR
         OLD.ground_truth_version IS DISTINCT FROM NEW.ground_truth_version OR
         OLD.dataset_hash IS DISTINCT FROM NEW.dataset_hash OR OLD.truncated IS DISTINCT FROM NEW.truncated OR
         OLD.versions_json IS DISTINCT FROM NEW.versions_json OR OLD.created_at IS DISTINCT FROM NEW.created_at OR
         OLD.status <> 'pending' OR NEW.status NOT IN ('completed','failed') THEN
        RAISE EXCEPTION 'IMMUTABLE_RECORD' USING ERRCODE='55000';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE FUNCTION app.guard_evaluation_item_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'IMMUTABLE_RECORD' USING ERRCODE='55000'; END $$""")
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)
    op.execute("""CREATE FUNCTION private.assigned_evaluation_truth(p_user uuid,p_run uuid)
RETURNS TABLE(run_id uuid,scenario_instance_id uuid,incident_key text,threat_label boolean,expected_evidence_keys jsonb,
                  explanation text,scenario_key text,truth_version integer)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,private,pg_temp AS $$
     SELECT et.run_id,et.scenario_instance_id,et.incident_key,et.threat_label,et.expected_evidence_keys,et.explanation,s.stable_key,
            et.truth_version
     FROM private.evaluation_truth et JOIN app.evaluations e ON e.id=et.evaluation_id AND e.run_id=et.run_id
     JOIN app.scenario_instances i ON i.run_id=et.run_id AND i.id=et.scenario_instance_id
     JOIN app.scenarios s ON s.id=i.scenario_id
     WHERE p_run=et.run_id AND e.status='completed'
     AND EXISTS(SELECT 1 FROM app.runs r JOIN app.instructor_assignments a ON a.analyst_user_id=r.owner_user_id
         WHERE r.id=p_run AND r.status='completed' AND a.instructor_user_id=p_user)
    $$""")
    op.execute("REVOKE ALL ON FUNCTION private.assigned_evaluation_truth(uuid,uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION private.assigned_evaluation_truth(uuid,uuid) TO api_runtime"
    )
    op.execute("""CREATE FUNCTION private.assigned_training_truth(p_user uuid,p_run uuid)
    RETURNS TABLE(run_id uuid,scenario_instance_id uuid,incident_key text,threat_label boolean,
                  expected_evidence_keys jsonb,explanation text,scenario_key text,truth_version integer)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,private,pg_temp AS $$
     SELECT r.id,i.id,g.incident_key,g.threat_label,g.expected_evidence_keys,g.explanation,s.stable_key,g.truth_version
     FROM app.runs r JOIN app.instructor_assignments a ON a.analyst_user_id=r.owner_user_id
     JOIN app.scenario_instances i ON i.run_id=r.id
     JOIN app.scenarios s ON s.id=i.scenario_id
     JOIN app.run_versions rv ON rv.run_id=r.id
     JOIN private.ground_truth g ON g.scenario_id=i.scenario_id
       AND g.truth_version=(rv.ground_truth_versions->>i.scenario_id::text)::integer
     WHERE r.id=p_run AND r.status IN ('running','paused','reviewing') AND a.instructor_user_id=p_user
    $$""")
    op.execute("REVOKE ALL ON FUNCTION private.assigned_training_truth(uuid,uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION private.assigned_training_truth(uuid,uuid) TO api_runtime"
    )
    op.execute("""CREATE FUNCTION private.owner_training_truth(p_user uuid,p_run uuid)
    RETURNS TABLE(run_id uuid,scenario_instance_id uuid,incident_key text,threat_label boolean,
                  expected_evidence_keys jsonb,explanation text,scenario_key text,truth_version integer)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,private,pg_temp AS $$
     SELECT et.run_id,et.scenario_instance_id,et.incident_key,et.threat_label,
            et.expected_evidence_keys,et.explanation,s.stable_key,et.truth_version
     FROM private.evaluation_truth et
     JOIN app.evaluations e ON e.id=et.evaluation_id AND e.run_id=et.run_id
     JOIN app.scenario_instances i ON i.run_id=et.run_id AND i.id=et.scenario_instance_id
     JOIN app.scenarios s ON s.id=i.scenario_id
     WHERE p_run=et.run_id AND e.status='completed'
     AND EXISTS(SELECT 1 FROM app.runs r WHERE r.id=p_run AND r.status='completed'
                AND r.owner_user_id=p_user)
    $$""")
    op.execute("REVOKE ALL ON FUNCTION private.owner_training_truth(uuid,uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION private.owner_training_truth(uuid,uuid) TO api_runtime")
    op.execute("""CREATE FUNCTION app.training_truth_version(p_scenario uuid) RETURNS integer
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,private,pg_temp AS $$
     SELECT coalesce(max(truth_version),1)::integer FROM private.ground_truth WHERE scenario_id=p_scenario
    $$""")
    op.execute("REVOKE ALL ON FUNCTION app.training_truth_version(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.training_truth_version(uuid) TO api_runtime")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
