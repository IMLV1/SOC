"""Dependency-aware source withdrawal without changing previously applied revisions."""

import importlib

revision = "0015_analysis_revocation"
down_revision = "0014_gemini_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute = importlib.import_module("migrations.versions.0012_knowledge").execute
    execute("""
    CREATE FUNCTION kb.analysis_revoked(analysis uuid) RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=kb,app,pg_temp AS $$
      SELECT EXISTS(SELECT 1 FROM app.retrieval_items i JOIN kb.versions v ON v.id=i.version_id
        WHERE i.analysis_id=analysis AND v.revoked_at IS NOT NULL)
    $$;
    REVOKE ALL ON FUNCTION kb.analysis_revoked(uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION kb.analysis_revoked(uuid) TO api_runtime,worker_runtime,
      evaluator_runtime;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
