"""Durable training runs, released evidence, and fenced work queue."""

from alembic import op

revision = "0004_runs_jobs"
down_revision = "0003_scenario_catalog"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.runs (
 id uuid PRIMARY KEY, owner_user_id uuid NOT NULL REFERENCES app.users(id),
 status text NOT NULL CHECK (status IN ('created','running','paused','reviewing','completing','completed','failed')),
 seed integer NOT NULL CHECK (seed BETWEEN 0 AND 2147483647),
 elapsed_ms bigint NOT NULL DEFAULT 0 CHECK (elapsed_ms >= 0), resumed_at timestamptz,
 release_cursor bigint NOT NULL DEFAULT 0 CHECK (release_cursor >= 0),
 duration_ms integer NOT NULL CHECK (duration_ms > 0),
 analysis_mode text NOT NULL DEFAULT 'mock' CHECK (analysis_mode = 'mock'),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 completing_at timestamptz, completed_at timestamptz, failure_code text,
 CHECK ((status = 'running') = (resumed_at IS NOT NULL))
);
CREATE UNIQUE INDEX one_running_run_per_owner ON app.runs(owner_user_id) WHERE status='running';
CREATE INDEX runs_owner_page ON app.runs(owner_user_id,created_at DESC,id);
CREATE INDEX runs_expiry ON app.runs(expires_at);
CREATE TABLE app.scenario_instances (
 id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES app.runs(id),
 scenario_id uuid NOT NULL REFERENCES app.scenarios(id), ordinal integer NOT NULL CHECK (ordinal BETWEEN 1 AND 5),
 UNIQUE(run_id,id), UNIQUE(run_id,ordinal), UNIQUE(run_id,scenario_id)
);
CREATE TABLE app.run_versions (
 run_id uuid PRIMARY KEY REFERENCES app.runs(id), rule_version text NOT NULL,
 baseline_version text NOT NULL, correlation_version text NOT NULL,
 ticket_policy_version text NOT NULL, prompt_version text NOT NULL,
 model_id text NOT NULL, fixture_hash text NOT NULL,
 config_snapshot jsonb NOT NULL CHECK (jsonb_typeof(config_snapshot)='object')
);
CREATE TABLE app.run_completions (
 run_id uuid PRIMARY KEY REFERENCES app.runs(id), revision integer NOT NULL,
 release_cutoff bigint NOT NULL, assessment_cutoff timestamptz NOT NULL,
 dataset_hash text NOT NULL, truncated boolean NOT NULL,
 drain_deadline timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.events (
 id uuid PRIMARY KEY, run_id uuid NOT NULL, scenario_instance_id uuid NOT NULL,
 fixture_event_key text NOT NULL, release_seq bigint NOT NULL CHECK (release_seq > 0),
 event_time timestamptz NOT NULL, ingested_at timestamptz NOT NULL DEFAULT now(),
 source text NOT NULL CHECK (source IN ('authentication','web','file_access','change_management','baseline')),
 asset_id text, username text, src_ip inet, request_json jsonb, response_json jsonb,
 log_json jsonb NOT NULL, content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
 UNIQUE(run_id,id), UNIQUE(run_id,release_seq),
 UNIQUE(run_id,scenario_instance_id,fixture_event_key),
 FOREIGN KEY (run_id,scenario_instance_id) REFERENCES app.scenario_instances(run_id,id)
);
CREATE INDEX event_time_page ON app.events(run_id,event_time,id);
CREATE INDEX event_asset_page ON app.events(run_id,asset_id,event_time,id);
CREATE INDEX event_source_page ON app.events(run_id,source,event_time,id);
CREATE INDEX event_ip_page ON app.events(run_id,src_ip,event_time,id);
CREATE TABLE app.jobs (
 id uuid PRIMARY KEY, run_id uuid REFERENCES app.runs(id), type text NOT NULL,
 dedupe_key text NOT NULL UNIQUE, payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 payload_version integer NOT NULL DEFAULT 1, status text NOT NULL DEFAULT 'queued'
 CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
 attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
 available_at timestamptz NOT NULL DEFAULT now(), lease_expires_at timestamptz,
 locked_by text, lease_token uuid, last_error text,
 created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
CREATE INDEX job_claim ON app.jobs(available_at,id) WHERE status='queued';
CREATE INDEX job_reclaim ON app.jobs(lease_expires_at,id) WHERE status='running';
CREATE TABLE app.worker_heartbeats (
 worker_id text PRIMARY KEY, role text NOT NULL, release_sha text NOT NULL,
 last_seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.idempotency_keys (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.users(id), method text NOT NULL,
 route_key text NOT NULL, key uuid NOT NULL, request_hash text NOT NULL,
 status text NOT NULL CHECK (status IN ('reserved','completed')),
 response_status integer, response_json jsonb, resource_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL,
 UNIQUE(user_id,method,route_key,key)
);
CREATE INDEX idempotency_expiry ON app.idempotency_keys(expires_at);
CREATE FUNCTION app.training_fixture_hash(p_scenario uuid) RETURNS text
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=app,pg_temp
 AS $$ SELECT fixture_hash FROM app.scenarios
       WHERE id=p_scenario AND enabled AND purpose='training' $$;
REVOKE ALL ON FUNCTION app.training_fixture_hash(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.training_fixture_hash(uuid) TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.runs,app.scenario_instances,app.run_versions,
 app.run_completions,app.jobs,app.idempotency_keys TO api_runtime;
GRANT SELECT ON app.events TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.runs,app.events,app.jobs,app.worker_heartbeats TO worker_runtime;
GRANT SELECT ON app.scenario_instances,app.scenarios,app.run_versions TO worker_runtime;
GRANT SELECT ON app.run_completions TO worker_runtime;
GRANT SELECT ON app.runs,app.events,app.jobs TO evaluator_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
