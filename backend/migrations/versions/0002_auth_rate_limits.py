"""Shared bounded-window counters for public authentication endpoints."""

from alembic import op

revision = "0002_auth_rate_limits"
down_revision = "0001_auth_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE app.auth_rate_limits (
        key_hash text NOT NULL CHECK(length(key_hash)=64),
        window_start timestamptz NOT NULL,
        request_count integer NOT NULL CHECK(request_count>0),
        PRIMARY KEY(key_hash,window_start))""")
    op.execute("CREATE INDEX auth_rate_expiry ON app.auth_rate_limits(window_start)")
    op.execute("GRANT SELECT,INSERT,UPDATE ON app.auth_rate_limits TO api_runtime")
    op.execute("GRANT SELECT,DELETE ON app.auth_rate_limits TO retention_runtime")


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration.")
