"""Versioned knowledge storage; vector extension is an admin prerequisite."""

from alembic import op


def execute(sql: str) -> None:
    # Split statements while preserving PL/pgSQL dollar-quoted bodies.
    parts = sql.split("$$")
    pending = ""
    for index, part in enumerate(parts):
        if index % 2:
            pending += "$$" + part + "$$"
        else:
            statements = part.split(";")
            pending += statements[0]
            for tail in statements[1:]:
                if pending.strip():
                    op.execute(pending)
                pending = tail
    if pending.strip():
        op.execute(pending)


revision = "0012_knowledge"
down_revision = "0011_provider_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector' AND extversion='0.8.2')
      THEN RAISE EXCEPTION 'Admin must install vector 0.8.2 before migration'; END IF;
    END $$""")
    execute("REVOKE ALL ON SCHEMA kb FROM PUBLIC")
    execute("""CREATE TABLE kb.profiles (
      id text PRIMARY KEY, model_id text NOT NULL, dimension int NOT NULL CHECK(dimension=16),
      mode text NOT NULL CHECK(mode='mock'), splitter_version text NOT NULL);
    INSERT INTO kb.profiles VALUES ('fake-hash-16-v1','fake-hash-16-v1',16,'mock','utf8-byte-v1');
    CREATE TABLE kb.versions (
      id uuid PRIMARY KEY, stable_key text NOT NULL, revision text NOT NULL,
      title text NOT NULL, language text NOT NULL, reviewer text NOT NULL,
      license text NOT NULL, content_hash text NOT NULL CHECK(length(content_hash)=64),
      body text NOT NULL, status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','ready')),
      revoked_at timestamptz, UNIQUE(stable_key,revision));
    CREATE TABLE kb.ingestions (
      id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES kb.versions(id),
      profile_id text NOT NULL REFERENCES kb.profiles(id),
      job_id uuid NOT NULL UNIQUE REFERENCES app.jobs(id),
      UNIQUE(version_id,profile_id));
    CREATE TABLE kb.chunks (
      id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES kb.versions(id),
      ordinal int NOT NULL CHECK(ordinal>=0), heading text NOT NULL,
      start_byte int NOT NULL CHECK(start_byte>=0), end_byte int NOT NULL,
      body text NOT NULL, content_hash text NOT NULL CHECK(length(content_hash)=64),
      CHECK(end_byte>start_byte), UNIQUE(version_id,ordinal));
    CREATE TABLE kb.embeddings_fake16 (
      chunk_id uuid PRIMARY KEY REFERENCES kb.chunks(id),
      embedding public.vector(16) NOT NULL CHECK(public.vector_norm(embedding)>0));
    CREATE TABLE kb.releases (
      id uuid PRIMARY KEY, manifest_hash text NOT NULL UNIQUE,
      profile_id text NOT NULL REFERENCES kb.profiles(id), published_at timestamptz);
    CREATE TABLE kb.members (
      release_id uuid NOT NULL REFERENCES kb.releases(id),
      version_id uuid NOT NULL REFERENCES kb.versions(id), PRIMARY KEY(release_id,version_id));
    CREATE TABLE kb.active_release (
      id int PRIMARY KEY CHECK(id=1), release_id uuid REFERENCES kb.releases(id),
      version int NOT NULL DEFAULT 1);
    INSERT INTO kb.active_release(id) VALUES(1);
    ALTER TABLE app.run_versions ADD COLUMN knowledge_release_id uuid REFERENCES kb.releases(id),
      ADD COLUMN retrieval_config_version text;
    GRANT USAGE ON SCHEMA kb TO api_runtime,worker_runtime;
    GRANT SELECT ON kb.releases,kb.active_release TO api_runtime;
    GRANT UPDATE(version) ON kb.active_release TO api_runtime;
    GRANT INSERT(knowledge_release_id,retrieval_config_version) ON app.run_versions TO api_runtime;
    GRANT SELECT ON kb.profiles,kb.versions,kb.ingestions,kb.chunks,kb.embeddings_fake16,
      kb.releases,kb.members TO worker_runtime;
    GRANT INSERT ON kb.chunks,kb.embeddings_fake16 TO worker_runtime;
    GRANT UPDATE(status) ON kb.versions TO worker_runtime;
    """)
    execute("""CREATE FUNCTION kb.guard_version() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR (to_jsonb(NEW)-'status'-'revoked_at') <>
        (to_jsonb(OLD)-'status'-'revoked_at') OR
        (OLD.status='ready' AND NEW.status<>'ready') OR
        (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
      THEN RAISE EXCEPTION 'immutable knowledge version'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER version_immutable BEFORE UPDATE OR DELETE ON kb.versions
      FOR EACH ROW EXECUTE FUNCTION kb.guard_version();
    CREATE FUNCTION kb.guard_ready_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM kb.versions WHERE id=NEW.version_id
        AND (status='ready' OR revoked_at IS NOT NULL))
      THEN RAISE EXCEPTION 'version is frozen'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER chunk_frozen BEFORE INSERT ON kb.chunks
      FOR EACH ROW EXECUTE FUNCTION kb.guard_ready_chunk();
    """)

    execute("""ALTER TABLE kb.versions ADD COLUMN audience text NOT NULL DEFAULT 'learner'
      CHECK(audience='learner');
    CREATE FUNCTION kb.current_release() RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
      SET search_path=kb,pg_temp AS $$
      SELECT r.id FROM kb.active_release a JOIN kb.releases r ON r.id=a.release_id
      WHERE a.id=1 AND r.published_at IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM kb.members m JOIN kb.versions v ON v.id=m.version_id
         WHERE m.release_id=r.id AND (v.revoked_at IS NOT NULL OR v.status<>'ready'))
    $$;
    REVOKE ALL ON FUNCTION kb.current_release() FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION kb.current_release() TO api_runtime;
    CREATE FUNCTION kb.guard_member() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM kb.releases WHERE id=NEW.release_id AND published_at IS NOT NULL)
      THEN
        IF TG_OP='INSERT' AND EXISTS(SELECT 1 FROM kb.members WHERE release_id=NEW.release_id
          AND version_id=NEW.version_id) THEN RETURN NULL; END IF;
        RAISE EXCEPTION 'published membership immutable';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER member_frozen BEFORE INSERT ON kb.members
      FOR EACH ROW EXECUTE FUNCTION kb.guard_member();
    REVOKE UPDATE,DELETE ON kb.chunks,kb.embeddings_fake16,kb.members,kb.profiles
      FROM worker_runtime;
    """)

    execute("""CREATE FUNCTION kb.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable knowledge snapshot'; END $$;
    CREATE TRIGGER chunks_immutable BEFORE UPDATE OR DELETE ON kb.chunks
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE TRIGGER embeddings_immutable BEFORE UPDATE OR DELETE ON kb.embeddings_fake16
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE TRIGGER profiles_immutable BEFORE UPDATE OR DELETE ON kb.profiles
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE TRIGGER membership_immutable BEFORE UPDATE OR DELETE ON kb.members
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE FUNCTION kb.guard_release() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.published_at IS NOT NULL OR
        (to_jsonb(NEW)-'published_at')<>(to_jsonb(OLD)-'published_at')
      THEN RAISE EXCEPTION 'immutable release'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER release_frozen BEFORE UPDATE ON kb.releases
      FOR EACH ROW EXECUTE FUNCTION kb.guard_release();
    CREATE TRIGGER release_delete BEFORE DELETE ON kb.releases
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    CREATE FUNCTION kb.guard_pin() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.knowledge_release_id IS NOT NULL AND
        (NEW.knowledge_release_id IS DISTINCT FROM OLD.knowledge_release_id OR
         NEW.retrieval_config_version IS DISTINCT FROM OLD.retrieval_config_version)
      THEN RAISE EXCEPTION 'immutable run knowledge pin'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER knowledge_pin BEFORE UPDATE ON app.run_versions
      FOR EACH ROW EXECUTE FUNCTION kb.guard_pin();
    """)

    execute("""CREATE TABLE kb.validations (
      release_id uuid NOT NULL REFERENCES kb.releases(id), suite_hash text NOT NULL,
      sample_count int NOT NULL CHECK(sample_count>0), passed boolean NOT NULL,
      membership_hash text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(release_id,suite_hash));
    CREATE TRIGGER validations_frozen BEFORE UPDATE OR DELETE ON kb.validations
      FOR EACH ROW EXECUTE FUNCTION kb.reject_mutation();
    """)

    execute("""GRANT USAGE ON SCHEMA app,kb TO knowledge_publisher,knowledge_ingestor;
    GRANT SELECT,INSERT ON kb.versions,kb.ingestions,kb.releases,kb.members,kb.validations
      TO knowledge_publisher;
    GRANT SELECT ON kb.profiles,kb.chunks,kb.embeddings_fake16 TO knowledge_publisher;
    GRANT SELECT,UPDATE ON kb.active_release TO knowledge_publisher;
    GRANT UPDATE(published_at) ON kb.releases TO knowledge_publisher;
    GRANT UPDATE(revoked_at) ON kb.versions TO knowledge_publisher;
    GRANT SELECT,INSERT ON app.jobs TO knowledge_publisher;
    GRANT INSERT ON app.audit_logs TO knowledge_publisher;
    GRANT SELECT ON kb.profiles,kb.versions,kb.ingestions,kb.chunks,kb.embeddings_fake16
      TO knowledge_ingestor;
    GRANT INSERT ON kb.chunks,kb.embeddings_fake16 TO knowledge_ingestor;
    GRANT UPDATE(status) ON kb.versions TO knowledge_ingestor;
    REVOKE INSERT ON kb.chunks,kb.embeddings_fake16 FROM worker_runtime;
    REVOKE UPDATE(status) ON kb.versions FROM worker_runtime;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use reviewed forward migration")
