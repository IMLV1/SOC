from alembic import context

config = context.config
connection = config.attributes.get("connection")
if connection is None or not config.attributes.get("migration_lock_held"):
    raise RuntimeError("Run python -m app.db.migrate; direct Alembic bypass is disabled.")

context.configure(
    connection=connection,
    version_table_schema="ops",
    transactional_ddl=True,
)
with context.begin_transaction():
    context.run_migrations()
