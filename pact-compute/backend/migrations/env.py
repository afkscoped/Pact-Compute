from alembic import context

from pact.db import Base, engine

if context.is_offline_mode():
    context.configure(dialect_name=engine.dialect.name, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
