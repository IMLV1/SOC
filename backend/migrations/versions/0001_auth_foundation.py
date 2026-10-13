"""Auth foundation only. Immutable once applied; no runs/exams/provider tables."""

from alembic import op

revision = "0001_auth_foundation"
down_revision = None
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.users (
 id uuid PRIMARY KEY,
 normalized_email varchar(254) NOT NULL UNIQUE,
 display_name varchar(60) NOT NULL CHECK (length(btrim(display_name)) BETWEEN 1 AND 60),
 password_hash text NOT NULL CHECK (password_hash LIKE '$argon2id$%'),
 role text NOT NULL CHECK (role IN ('analyst','instructor')),
 status text NOT NULL CHECK (status IN ('active','disabled')),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (normalized_email = lower(btrim(normalized_email)) AND length(normalized_email) > 3)
);
CREATE TABLE app.auth_sessions (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.users(id),
 token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
 csrf_hash text NOT NULL CHECK (csrf_hash ~ '^[0-9a-f]{64}$'),
 expires_at timestamptz NOT NULL, revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), CHECK (expires_at > created_at)
);
CREATE INDEX sessions_user ON app.auth_sessions(user_id);
CREATE INDEX sessions_expiry ON app.auth_sessions(expires_at);
CREATE TABLE app.auth_challenges (
 id uuid PRIMARY KEY,
 token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
 csrf_hash text NOT NULL CHECK (csrf_hash ~ '^[0-9a-f]{64}$'),
 expires_at timestamptz NOT NULL, consumed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), CHECK (expires_at > created_at)
);
CREATE INDEX challenges_expiry ON app.auth_challenges(expires_at);
CREATE TABLE app.user_quotas (
 user_id uuid PRIMARY KEY REFERENCES app.users(id),
 daily_runs integer NOT NULL CHECK (daily_runs >= 0),
 daily_ai_requests integer NOT NULL CHECK (daily_ai_requests >= 0),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.instructor_assignments (
 instructor_user_id uuid NOT NULL REFERENCES app.users(id),
 analyst_user_id uuid NOT NULL REFERENCES app.users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(instructor_user_id,analyst_user_id),
 CHECK (instructor_user_id <> analyst_user_id)
);
CREATE INDEX assignments_analyst ON app.instructor_assignments(analyst_user_id);
CREATE TABLE app.quota_ledgers (
 id uuid PRIMARY KEY, scope_key text NOT NULL,
 user_id uuid REFERENCES app.users(id), period_start date NOT NULL,
 run_count integer NOT NULL DEFAULT 0 CHECK (run_count >= 0),
 ai_request_count integer NOT NULL DEFAULT 0 CHECK (ai_request_count >= 0),
 reserved_tokens bigint NOT NULL DEFAULT 0 CHECK (reserved_tokens >= 0),
 consumed_tokens bigint NOT NULL DEFAULT 0 CHECK (consumed_tokens >= 0),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 UNIQUE(scope_key,period_start),
 CHECK ((scope_key='system' AND user_id IS NULL) OR
        (user_id IS NOT NULL AND scope_key='user:' || user_id::text))
);
CREATE TABLE app.audit_logs (
 id uuid PRIMARY KEY,
 actor_user_id uuid REFERENCES app.users(id),
 actor_role text NOT NULL CHECK (actor_role IN ('analyst','instructor','system')),
 action text NOT NULL, entity_type text NOT NULL, entity_id uuid,
 before_json jsonb, after_json jsonb, reason text, request_id text,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_entity ON app.audit_logs(entity_type,entity_id,created_at,id);
CREATE INDEX audit_time ON app.audit_logs(created_at,id);
GRANT USAGE ON SCHEMA app TO api_runtime,worker_runtime,evaluator_runtime,retention_runtime;
GRANT USAGE ON SCHEMA ops TO api_runtime,worker_runtime,evaluator_runtime,retention_runtime;
GRANT SELECT ON ops.alembic_version,ops.schema_migrations
 TO api_runtime,worker_runtime,evaluator_runtime,retention_runtime;
GRANT SELECT,INSERT,UPDATE ON app.users,app.auth_sessions,app.auth_challenges,
 app.user_quotas,app.quota_ledgers TO api_runtime;
GRANT SELECT ON app.instructor_assignments TO api_runtime;
GRANT SELECT,INSERT ON app.audit_logs TO api_runtime;
GRANT INSERT ON app.audit_logs TO worker_runtime,evaluator_runtime;
GRANT SELECT,DELETE ON app.auth_sessions,app.auth_challenges,app.audit_logs TO retention_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
