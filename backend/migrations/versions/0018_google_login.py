"""Google subject identities and short-lived single-use browser-bound flows."""

from alembic import op

revision = "0018_google_login"
down_revision = "0017_provider_telemetry"
branch_labels = None
depends_on = None

DDL = """
ALTER TABLE app.users ALTER COLUMN password_hash DROP NOT NULL;
CREATE TABLE app.google_identities (
 user_id uuid PRIMARY KEY REFERENCES app.users(id),
 issuer text NOT NULL CHECK(issuer='https://accounts.google.com'),
 subject varchar(255) NOT NULL CHECK(length(subject)>0),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(issuer,subject)
);
CREATE TABLE app.google_flows (
 state_hash text PRIMARY KEY CHECK(state_hash ~ '^[0-9a-f]{64}$'),
 binding_hash text NOT NULL CHECK(binding_hash ~ '^[0-9a-f]{64}$'),
 session_hash text NOT NULL CHECK(session_hash ~ '^[0-9a-f]{64}$'),
 nonce_hash text NOT NULL CHECK(nonce_hash ~ '^[0-9a-f]{64}$'),
 verifier text CHECK(verifier ~ '^[A-Za-z0-9_-]{43,128}$'),
 purpose text NOT NULL CHECK(purpose IN ('login','link')),
 user_id uuid REFERENCES app.users(id), session_id uuid REFERENCES app.auth_sessions(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes', consumed_at timestamptz,
 CHECK(expires_at>created_at),
 CHECK((purpose='login' AND user_id IS NULL AND session_id IS NULL) OR
       (purpose='link' AND user_id IS NOT NULL AND session_id IS NOT NULL)),
 CHECK((consumed_at IS NULL) = (verifier IS NOT NULL))
);
CREATE INDEX google_flows_expiry ON app.google_flows(expires_at);
GRANT SELECT,INSERT ON app.google_identities TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.google_flows TO api_runtime;
GRANT SELECT,DELETE ON app.google_flows TO retention_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
