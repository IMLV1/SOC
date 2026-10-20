"""Versioned learning lessons and server-owned progress."""

from alembic import op

revision = "0019_learning_path"
down_revision = "0018_google_login"
branch_labels = None
depends_on = None

DDL = """
CREATE TABLE app.learning_levels (
 id uuid PRIMARY KEY, ordinal integer NOT NULL CHECK(ordinal BETWEEN 1 AND 3),
 title text NOT NULL, enabled boolean NOT NULL DEFAULT true,
 version integer NOT NULL CHECK(version>0),
 UNIQUE(ordinal,version)
);
CREATE TABLE app.lessons (
 id uuid PRIMARY KEY, level_id uuid NOT NULL REFERENCES app.learning_levels(id),
 version integer NOT NULL CHECK(version>0), title text NOT NULL, content_json jsonb NOT NULL,
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 published_at timestamptz NOT NULL,
 UNIQUE(id,version), CHECK(jsonb_typeof(content_json)='object')
);
CREATE TABLE app.user_lesson_progress (
 user_id uuid NOT NULL REFERENCES app.users(id), lesson_id uuid NOT NULL,
 lesson_version integer NOT NULL, completed_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
 completed_at timestamptz, version integer NOT NULL DEFAULT 0 CHECK(version>=0),
 updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(user_id,lesson_id),
 FOREIGN KEY(lesson_id,lesson_version) REFERENCES app.lessons(id,version),
 CHECK(jsonb_typeof(completed_steps)='array'),
 CHECK((completed_at IS NULL) OR jsonb_array_length(completed_steps)>0)
);
GRANT SELECT ON app.learning_levels,app.lessons TO api_runtime;
GRANT SELECT,INSERT,UPDATE ON app.user_lesson_progress TO api_runtime;
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade disabled")
