"""Append-only human assessment and versioned investigation notes."""

from alembic import op

revision = "0006_investigation_history"
down_revision = "0005_detection_tickets"
branch_labels = None
depends_on = None

DDL = """
ALTER TABLE app.audit_logs ADD COLUMN run_id uuid REFERENCES app.runs(id);
CREATE INDEX audit_run_time ON app.audit_logs(run_id,created_at,id);
CREATE TABLE app.assessments (
 id uuid PRIMARY KEY,run_id uuid NOT NULL,ticket_id uuid NOT NULL,
 revision integer NOT NULL CHECK (revision > 0),
 author_user_id uuid NOT NULL REFERENCES app.users(id),
 disposition text NOT NULL CHECK (disposition IN ('true_positive','false_positive','undetermined')),
 reason varchar(2000) NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 2000),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(ticket_id,revision),
 FOREIGN KEY(run_id,ticket_id) REFERENCES app.tickets(run_id,id)
);
CREATE TABLE app.notes (
 id uuid PRIMARY KEY,run_id uuid NOT NULL,ticket_id uuid NOT NULL,
 owner_user_id uuid NOT NULL REFERENCES app.users(id),
 body varchar(2000) NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 2000),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 deleted_at timestamptz,deleted_by uuid REFERENCES app.users(id),delete_reason text,
 UNIQUE(run_id,ticket_id,id),
 FOREIGN KEY(run_id,ticket_id) REFERENCES app.tickets(run_id,id),
 CHECK ((deleted_at IS NULL AND deleted_by IS NULL AND delete_reason IS NULL) OR
        (deleted_at IS NOT NULL AND deleted_by IS NOT NULL AND delete_reason IS NOT NULL))
);
CREATE TABLE app.note_evidence (
 run_id uuid NOT NULL,ticket_id uuid NOT NULL,note_id uuid NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(note_id,event_id),
 FOREIGN KEY(run_id,ticket_id,note_id) REFERENCES app.notes(run_id,ticket_id,id),
 FOREIGN KEY(run_id,ticket_id,event_id) REFERENCES app.ticket_events(run_id,ticket_id,event_id)
);
CREATE TABLE app.note_versions (
 id uuid PRIMARY KEY,run_id uuid NOT NULL,ticket_id uuid NOT NULL,note_id uuid NOT NULL,
 version integer NOT NULL CHECK (version > 0),body varchar(2000) NOT NULL,
 change_kind text NOT NULL CHECK (change_kind IN ('create','edit','delete','restore')),
 reason text,actor_user_id uuid NOT NULL REFERENCES app.users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(note_id,version),UNIQUE(run_id,id),
 FOREIGN KEY(run_id,ticket_id,note_id) REFERENCES app.notes(run_id,ticket_id,id)
);
CREATE TABLE app.note_version_evidence (
 run_id uuid NOT NULL,note_version_id uuid NOT NULL,event_id uuid NOT NULL,
 PRIMARY KEY(note_version_id,event_id),
 FOREIGN KEY(run_id,note_version_id) REFERENCES app.note_versions(run_id,id),
 FOREIGN KEY(run_id,event_id) REFERENCES app.events(run_id,id)
);
GRANT SELECT,INSERT ON app.assessments,app.note_versions,app.note_version_evidence TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.notes TO api_runtime;
GRANT SELECT,INSERT,DELETE ON app.note_evidence TO api_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
