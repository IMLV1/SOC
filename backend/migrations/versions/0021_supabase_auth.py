"""Supabase subject binding and encrypted server-side provider sessions."""

from alembic import op

revision = "0021_supabase_auth"
down_revision = "0020_exam_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in """
    CREATE TABLE app.supabase_identities (
      subject uuid PRIMARY KEY, user_id uuid NOT NULL UNIQUE REFERENCES app.users(id),
      created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE app.supabase_sessions (
      session_id uuid PRIMARY KEY REFERENCES app.auth_sessions(id),
      subject uuid NOT NULL REFERENCES app.supabase_identities(subject),
      provider_session_id uuid NOT NULL,
      encrypted_tokens text NOT NULL, access_expires_at timestamptz NOT NULL,
      version integer NOT NULL DEFAULT 1 CHECK(version>0),
      refresh_lease uuid, refresh_deadline timestamptz);
    CREATE TABLE app.supabase_flows (
      binding_hash text PRIMARY KEY, session_hash text NOT NULL,
      verifier text, expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes',
      consumed_at timestamptz,
      CHECK((verifier IS NULL)=(consumed_at IS NOT NULL)));
    GRANT SELECT,INSERT ON app.supabase_identities TO api_runtime;
    GRANT SELECT,INSERT,UPDATE ON app.supabase_sessions,app.supabase_flows TO api_runtime;
    GRANT SELECT,DELETE ON app.supabase_sessions,app.supabase_flows TO retention_runtime;
    """.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use reviewed forward migration")
