"""Bind each frozen citation version to its immutable chunk."""

from alembic import op

revision = "0016_rag_scope"
down_revision = "0015_analysis_revocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE kb.chunks ADD UNIQUE(id,version_id)")
    op.execute("""ALTER TABLE app.retrieval_items ADD CONSTRAINT retrieval_chunk_version
      FOREIGN KEY(chunk_id,version_id) REFERENCES kb.chunks(id,version_id)""")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
