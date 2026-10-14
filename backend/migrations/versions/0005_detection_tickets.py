"""Versioned detections, alerts, and idempotent automatic tickets."""

from alembic import op

revision = "0005_detection_tickets"
down_revision = "0004_runs_jobs"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.detections (
 id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES app.runs(id),
 detector_type text NOT NULL CHECK (detector_type IN ('rule','anomaly')),
 detector_version text NOT NULL, correlation_key text NOT NULL,
 evidence_snapshot_hash text NOT NULL CHECK (evidence_snapshot_hash ~ '^[0-9a-f]{64}$'),
 severity text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
 explanation text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(run_id,id),
 UNIQUE(run_id,detector_type,detector_version,correlation_key,evidence_snapshot_hash)
);
CREATE TABLE app.detection_evidence (
 run_id uuid NOT NULL, detection_id uuid NOT NULL, event_id uuid NOT NULL,
 PRIMARY KEY(detection_id,event_id),
 FOREIGN KEY(run_id,detection_id) REFERENCES app.detections(run_id,id),
 FOREIGN KEY(run_id,event_id) REFERENCES app.events(run_id,id)
);
CREATE TABLE app.alerts (
 id uuid PRIMARY KEY, run_id uuid NOT NULL, detection_id uuid NOT NULL,
 severity text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(run_id,id), UNIQUE(run_id,detection_id),
 FOREIGN KEY(run_id,detection_id) REFERENCES app.detections(run_id,id)
);
CREATE TABLE app.tickets (
 id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES app.runs(id),
 origin text NOT NULL CHECK (origin IN ('automatic','manual')),
 correlation_key text, title varchar(120) NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 120),
 severity text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
 human_severity_override boolean NOT NULL DEFAULT false,
 status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','investigating','resolved','closed')),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 deleted_at timestamptz, deleted_by uuid REFERENCES app.users(id), delete_reason text,
 UNIQUE(run_id,id),
 CHECK ((origin='automatic' AND correlation_key IS NOT NULL) OR
        (origin='manual' AND correlation_key IS NULL)),
 CHECK ((deleted_at IS NULL AND deleted_by IS NULL AND delete_reason IS NULL) OR
        (deleted_at IS NOT NULL AND delete_reason IS NOT NULL))
);
CREATE UNIQUE INDEX one_automatic_ticket_per_correlation
 ON app.tickets(run_id,correlation_key) WHERE origin='automatic';
CREATE INDEX ticket_open_page ON app.tickets(run_id,status,severity,id) WHERE deleted_at IS NULL;
CREATE TABLE app.ticket_events (
 run_id uuid NOT NULL,ticket_id uuid NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(ticket_id,event_id), UNIQUE(run_id,ticket_id,event_id),
 FOREIGN KEY(run_id,ticket_id) REFERENCES app.tickets(run_id,id),
 FOREIGN KEY(run_id,event_id) REFERENCES app.events(run_id,id)
);
CREATE TABLE app.ticket_alerts (
 run_id uuid NOT NULL,ticket_id uuid NOT NULL,alert_id uuid NOT NULL,
 PRIMARY KEY(ticket_id,alert_id),
 FOREIGN KEY(run_id,ticket_id) REFERENCES app.tickets(run_id,id),
 FOREIGN KEY(run_id,alert_id) REFERENCES app.alerts(run_id,id)
);
GRANT SELECT ON app.detections,app.detection_evidence,app.alerts TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.tickets TO api_runtime;
GRANT SELECT,INSERT,DELETE ON app.ticket_events,app.ticket_alerts TO api_runtime;
GRANT SELECT,INSERT ON app.detections,app.detection_evidence,app.alerts,
 app.ticket_events,app.ticket_alerts TO worker_runtime;
GRANT SELECT,INSERT,UPDATE ON app.tickets TO worker_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
