"""Frozen retrievals, question analyses and scoped revocation projection."""

import importlib

revision = "0013_rag"
down_revision = "0012_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute = importlib.import_module("migrations.versions.0012_knowledge").execute
    execute("""
    CREATE FUNCTION app.is_training_run(run uuid) RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,pg_temp AS $$
      SELECT EXISTS(SELECT 1 FROM app.scenario_instances WHERE run_id=run) AND NOT EXISTS(
        SELECT 1 FROM app.scenario_instances i JOIN app.scenarios s ON s.id=i.scenario_id
        WHERE i.run_id=run AND s.purpose<>'training')
    $$;
    REVOKE ALL ON FUNCTION app.is_training_run(uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app.is_training_run(uuid) TO api_runtime,worker_runtime;
    ALTER TABLE app.analyses ADD COLUMN kind text NOT NULL DEFAULT 'triage'
      CHECK(kind IN ('triage','question')),
      ADD COLUMN question_text text, ADD COLUMN question_hash text,
      ADD COLUMN ticket_id uuid, ADD COLUMN knowledge_release_id uuid REFERENCES kb.releases(id),
      ADD COLUMN retrieval_config_version text,
      ADD CONSTRAINT analysis_ticket_scope FOREIGN KEY(run_id,ticket_id)
        REFERENCES app.tickets(run_id,id),
      ADD CONSTRAINT question_fields CHECK(
        (kind='question' AND length(btrim(question_text)) BETWEEN 1 AND 2000
          AND question_hash IS NOT NULL AND ticket_id IS NOT NULL
          AND knowledge_release_id IS NOT NULL) OR
        (kind='triage' AND question_text IS NULL AND question_hash IS NULL));
    CREATE TABLE app.retrievals (
      id uuid PRIMARY KEY, run_id uuid NOT NULL, analysis_id uuid NOT NULL UNIQUE,
      release_id uuid NOT NULL REFERENCES kb.releases(id), config_version text NOT NULL,
      status text NOT NULL CHECK(status IN ('matched','no_match','unavailable')),
      query_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(run_id,analysis_id,id),
      FOREIGN KEY(run_id,analysis_id) REFERENCES app.analyses(run_id,id));
    CREATE TABLE app.retrieval_items (
      id uuid PRIMARY KEY, run_id uuid NOT NULL,analysis_id uuid NOT NULL,
      retrieval_id uuid NOT NULL,
      chunk_id uuid NOT NULL REFERENCES kb.chunks(id),
      version_id uuid NOT NULL REFERENCES kb.versions(id),
      rank integer NOT NULL CHECK(rank BETWEEN 1 AND 5),score double precision NOT NULL,
      excerpt_snapshot text NOT NULL,content_hash text NOT NULL,document_title text NOT NULL,
      document_version text NOT NULL,heading text NOT NULL,
      UNIQUE(retrieval_id,chunk_id),UNIQUE(run_id,analysis_id,id),
      FOREIGN KEY(run_id,analysis_id,retrieval_id)
        REFERENCES app.retrievals(run_id,analysis_id,id));
    CREATE TABLE app.analysis_knowledge_refs (
      run_id uuid NOT NULL,analysis_id uuid NOT NULL,retrieval_item_id uuid NOT NULL,
      PRIMARY KEY(analysis_id,retrieval_item_id),
      FOREIGN KEY(run_id,analysis_id,retrieval_item_id)
        REFERENCES app.retrieval_items(run_id,analysis_id,id));
    CREATE TABLE app.quota_components (
      analysis_id uuid NOT NULL REFERENCES app.analyses(id),component text NOT NULL
        CHECK(component IN ('query_embedding','generation')),
      model_id text NOT NULL,reserved_tokens bigint NOT NULL CHECK(reserved_tokens>=0),
      actual_tokens bigint,status text NOT NULL DEFAULT 'reserved'
        CHECK(status IN ('reserved','consumed','released','unknown')),
      measured_cost numeric, PRIMARY KEY(analysis_id,component));
    GRANT SELECT,INSERT ON app.retrievals,app.retrieval_items,app.analysis_knowledge_refs
      TO worker_runtime;
    GRANT INSERT ON app.retrievals,app.retrieval_items TO api_runtime;
    GRANT SELECT ON app.retrievals,app.retrieval_items,app.analysis_knowledge_refs
      TO api_runtime,evaluator_runtime;
    GRANT SELECT,INSERT,UPDATE ON app.quota_components TO worker_runtime,api_runtime;
    GRANT UPDATE(kind,question_text,question_hash,ticket_id,knowledge_release_id,
      retrieval_config_version) ON app.analyses TO api_runtime;
    CREATE FUNCTION kb.release_revoked(release uuid) RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=kb,pg_temp AS $$
      SELECT EXISTS(SELECT 1 FROM kb.members m JOIN kb.versions v ON v.id=m.version_id
        WHERE m.release_id=release AND v.revoked_at IS NOT NULL)
    $$;
    REVOKE ALL ON FUNCTION kb.release_revoked(uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION kb.release_revoked(uuid) TO api_runtime,worker_runtime,
      evaluator_runtime;
    CREATE TRIGGER retrieval_frozen BEFORE UPDATE OR DELETE ON app.retrievals
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE TRIGGER retrieval_item_frozen BEFORE UPDATE OR DELETE ON app.retrieval_items
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE TRIGGER knowledge_ref_frozen BEFORE UPDATE OR DELETE ON app.analysis_knowledge_refs
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE FUNCTION app.guard_analysis_context() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.kind,NEW.question_text,NEW.question_hash,NEW.ticket_id,
          NEW.knowledge_release_id,NEW.retrieval_config_version) IS DISTINCT FROM
         (OLD.kind,OLD.question_text,OLD.question_hash,OLD.ticket_id,
          OLD.knowledge_release_id,OLD.retrieval_config_version)
      THEN RAISE EXCEPTION 'immutable analysis context'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER analysis_context_frozen BEFORE UPDATE ON app.analyses
      FOR EACH ROW EXECUTE FUNCTION app.guard_analysis_context();
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
