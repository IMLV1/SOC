"""Frozen mock analysis snapshots, attempts, and quota reservations."""

from alembic import op

revision = "0007_mock_analysis"
down_revision = "0006_investigation_history"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.analyses (
 id uuid PRIMARY KEY,run_id uuid NOT NULL REFERENCES app.runs(id),
 correlation_key text NOT NULL,evidence_hash text NOT NULL,
 attempt_group uuid NOT NULL,retry_of uuid,
 mode text NOT NULL CHECK (mode='mock'),model_id text NOT NULL,prompt_version text NOT NULL,
 status text NOT NULL CHECK (status IN ('queued','running','succeeded','failed',
  'invalid_output','quota_exceeded','timed_out','cancelled')),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 result_json jsonb,error_code text,usage_json jsonb,latency_ms integer,
 created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,finished_at timestamptz,
 UNIQUE(run_id,id),
 UNIQUE(run_id,correlation_key,evidence_hash,model_id,prompt_version,attempt_group),
 FOREIGN KEY(run_id,retry_of) REFERENCES app.analyses(run_id,id)
);
CREATE TABLE app.analysis_evidence (
 run_id uuid NOT NULL,analysis_id uuid NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(analysis_id,event_id),
 FOREIGN KEY(run_id,analysis_id) REFERENCES app.analyses(run_id,id),
 FOREIGN KEY(run_id,event_id) REFERENCES app.events(run_id,id)
);
CREATE TABLE app.analysis_attempts (
 id uuid PRIMARY KEY,run_id uuid NOT NULL,analysis_id uuid NOT NULL,
 attempt_no integer NOT NULL CHECK (attempt_no > 0),provider_request_id text,
 status text NOT NULL,started_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz,error_code text,usage_json jsonb,
 UNIQUE(analysis_id,attempt_no),
 FOREIGN KEY(run_id,analysis_id) REFERENCES app.analyses(run_id,id)
);
CREATE TABLE app.quota_reservations (
 id uuid PRIMARY KEY,run_id uuid NOT NULL REFERENCES app.runs(id),
 analysis_id uuid NOT NULL REFERENCES app.analyses(id),
 ledger_id uuid NOT NULL REFERENCES app.quota_ledgers(id),
 reserved_tokens bigint NOT NULL DEFAULT 0 CHECK (reserved_tokens >= 0),
 actual_tokens bigint,status text NOT NULL CHECK (status IN ('reserved','consumed','released','unknown')),
 created_at timestamptz NOT NULL DEFAULT now(),settled_at timestamptz,
 UNIQUE(analysis_id,ledger_id)
);
CREATE TABLE app.ticket_analyses (
 run_id uuid NOT NULL,ticket_id uuid NOT NULL,analysis_id uuid NOT NULL,
 PRIMARY KEY(ticket_id,analysis_id),
 FOREIGN KEY(run_id,ticket_id) REFERENCES app.tickets(run_id,id),
 FOREIGN KEY(run_id,analysis_id) REFERENCES app.analyses(run_id,id)
);
GRANT SELECT ON app.analyses,app.analysis_evidence,app.analysis_attempts,
 app.quota_reservations,app.ticket_analyses TO api_runtime;
GRANT INSERT ON app.analyses,app.analysis_evidence,app.quota_reservations,
 app.ticket_analyses,app.jobs TO worker_runtime;
GRANT SELECT,UPDATE ON app.analyses,app.quota_reservations TO worker_runtime;
GRANT SELECT ON app.analysis_evidence TO worker_runtime;
GRANT SELECT,INSERT,UPDATE ON app.analysis_attempts TO worker_runtime;
GRANT SELECT,INSERT,UPDATE ON app.quota_ledgers TO worker_runtime;
GRANT SELECT(daily_ai_requests,user_id) ON app.user_quotas TO worker_runtime;
GRANT INSERT ON app.analyses,app.analysis_evidence,
 app.quota_reservations,app.ticket_analyses TO api_runtime;
GRANT UPDATE(status,error_code,finished_at,version) ON app.analyses TO api_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
