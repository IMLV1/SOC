"""Selected Gemini 768 profile, shared dispatch caps for embedding and generation."""

import importlib

revision = "0014_gemini_rag"
down_revision = "0013_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute = importlib.import_module("migrations.versions.0012_knowledge").execute
    execute("""
    GRANT SELECT ON app.provider_policy,app.provider_calls TO api_runtime;
    GRANT UPDATE(version) ON app.provider_policy TO api_runtime;
    ALTER TABLE kb.profiles DROP CONSTRAINT profiles_dimension_check,
      DROP CONSTRAINT profiles_mode_check;
    ALTER TABLE kb.profiles ADD CHECK((dimension=16 AND mode='mock') OR
      (dimension=768 AND mode='real'));
    INSERT INTO kb.profiles VALUES ('gemini-embedding-2-768-v1','gemini-embedding-2',
      768,'real','utf8-byte-v1');
    CREATE TABLE kb.retrieval_policies (
      release_id uuid PRIMARY KEY REFERENCES kb.releases(id),max_distance double precision NOT NULL
      CHECK(max_distance>0 AND max_distance<2),calibration_hash text NOT NULL);
    CREATE TRIGGER retrieval_policy_frozen BEFORE UPDATE OR DELETE ON kb.retrieval_policies
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    GRANT SELECT ON kb.retrieval_policies TO worker_runtime,knowledge_publisher;
    GRANT INSERT ON kb.retrieval_policies TO knowledge_publisher;
    CREATE TABLE kb.embeddings_gemini768 (
      chunk_id uuid PRIMARY KEY REFERENCES kb.chunks(id),
      embedding public.vector(768) NOT NULL CHECK(public.vector_norm(embedding)>0));
    CREATE TRIGGER embeddings_gemini_frozen BEFORE UPDATE OR DELETE ON kb.embeddings_gemini768
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    GRANT SELECT ON kb.embeddings_gemini768 TO worker_runtime,
      knowledge_publisher,knowledge_ingestor;
    GRANT INSERT ON kb.embeddings_gemini768 TO knowledge_ingestor;
    ALTER TABLE app.provider_calls DROP CONSTRAINT provider_calls_analysis_id_key,
      DROP CONSTRAINT provider_calls_component_check,DROP CONSTRAINT provider_calls_check1;
    ALTER TABLE app.provider_calls ADD COLUMN operation_key text UNIQUE,
      ADD UNIQUE(analysis_id,component),
      ADD CHECK(component IN ('generation','query_embedding','document_embedding')),
      ADD CHECK(num_nonnulls(analysis_id,experiment_arm_id,operation_key)=1);
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
