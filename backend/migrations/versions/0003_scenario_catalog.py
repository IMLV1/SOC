"""Training-only catalog and evaluator-only truth; no runs or exam admission."""

from alembic import op

revision = "0003_scenario_catalog"
down_revision = "0002_auth_rate_limits"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.scenarios (
 id uuid PRIMARY KEY,
 stable_key text NOT NULL CHECK (stable_key ~ '^S0[1-5]$'),
 version integer NOT NULL CHECK (version > 0),
 purpose text NOT NULL CHECK (purpose = 'training'),
 public_title varchar(120) NOT NULL,
 difficulty text NOT NULL CHECK (difficulty IN ('beginner','intermediate','advanced')),
 duration_ms integer NOT NULL CHECK (duration_ms > 0),
 learning_objectives jsonb NOT NULL CHECK (jsonb_typeof(learning_objectives) = 'array'),
 enabled boolean NOT NULL,
 fixture_hash text NOT NULL CHECK (fixture_hash ~ '^[0-9a-f]{64}$'),
 seed_hash text NOT NULL CHECK (seed_hash ~ '^[0-9a-f]{64}$'),
 UNIQUE(stable_key,version)
);
CREATE TABLE private.ground_truth (
 id uuid PRIMARY KEY,
 scenario_id uuid NOT NULL REFERENCES app.scenarios(id),
 truth_version integer NOT NULL CHECK (truth_version > 0),
 incident_key text NOT NULL,
 threat_label boolean NOT NULL,
 expected_evidence_keys jsonb NOT NULL CHECK (jsonb_typeof(expected_evidence_keys) = 'array'),
 explanation text NOT NULL,
 content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
 UNIQUE(scenario_id,truth_version,incident_key)
);
GRANT SELECT(id,version,public_title,difficulty,duration_ms,learning_objectives,enabled)
 ON app.scenarios TO api_runtime;
GRANT SELECT ON app.scenarios TO worker_runtime,evaluator_runtime;
GRANT USAGE ON SCHEMA private TO evaluator_runtime;
GRANT SELECT ON private.ground_truth TO evaluator_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled; use a reviewed forward migration.")
