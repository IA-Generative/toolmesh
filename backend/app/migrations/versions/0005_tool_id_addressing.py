"""tools addressed by id: a name is unique within its source, not across sources

The names the registry had to rename (`<source>.<tool>`) get their own back, and the search log (results, clicks,
expected tools of the verdicts) now holds tool ids instead of names.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

tools = sa.table("tools", sa.column("id", sa.String), sa.column("name", sa.String), sa.column("remote_name", sa.String))
events = sa.table("search_events", sa.column("id", sa.String), sa.column("results", sa.JSON))
clicks = sa.table("search_clicks", sa.column("id", sa.String), sa.column("tool", sa.String))
feedback = sa.table("search_feedback", sa.column("id", sa.String), sa.column("expected", sa.JSON))


def _swap(conn, mapping: dict[str, str]) -> None:
    """Replace the tool references of the search log with `mapping`; what is not in it (a deleted tool) is dropped."""
    for row in conn.execute(sa.select(events.c.id, events.c.results)):
        conn.execute(
            events.update()
            .where(events.c.id == row.id)
            .values(results=[mapping[n] for n in row.results if n in mapping])
        )
    for row in conn.execute(sa.select(feedback.c.id, feedback.c.expected)):
        conn.execute(
            feedback.update()
            .where(feedback.c.id == row.id)
            .values(expected=[mapping[n] for n in row.expected if n in mapping])
        )
    for row in conn.execute(sa.select(clicks.c.id, clicks.c.tool)):
        if row.tool in mapping:
            conn.execute(clicks.update().where(clicks.c.id == row.id).values(tool=mapping[row.tool]))
        else:
            conn.execute(clicks.delete().where(clicks.c.id == row.id))


# SQLite cannot alter a constraint: the table is rebuilt, and its unnamed unique gets the name given by this convention.
SQLITE_NAMES = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    conn = op.get_bind()
    by_name = {r.name: r.id for r in conn.execute(sa.select(tools.c.id, tools.c.name))}
    _swap(conn, by_name)
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("tools", naming_convention=SQLITE_NAMES) as batch:
            batch.drop_constraint("uq_tools_name", type_="unique")
            batch.create_unique_constraint("uq_tools_source_id_name", ["source_id", "name"])
    else:
        op.drop_constraint("tools_name_key", "tools", type_="unique")
        op.create_unique_constraint("uq_tools_source_id_name", "tools", ["source_id", "name"])
    conn.execute(tools.update().where(tools.c.remote_name.is_not(None)).values(name=tools.c.remote_name))
    op.drop_column("tools", "remote_name")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("tools") as batch:
            batch.drop_constraint("uq_tools_source_id_name", type_="unique")
            batch.add_column(sa.Column("remote_name", sa.String(100)))
    else:
        op.drop_constraint("uq_tools_source_id_name", "tools", type_="unique")
        op.add_column("tools", sa.Column("remote_name", sa.String(100)))
    # A name taken by several sources is renamed `<source>.<tool>` again, for all but the first.
    rows = conn.execute(
        sa.text(
            "SELECT t.id, t.name, s.name AS source FROM tools t JOIN sources s ON s.id = t.source_id"
            " ORDER BY s.created_at, t.id"
        )
    ).all()
    seen: set[str] = set()
    for row in rows:
        if row.name in seen:
            conn.execute(
                tools.update()
                .where(tools.c.id == row.id)
                .values(name=f"{row.source}.{row.name}"[:100], remote_name=row.name)
            )
        seen.add(row.name)
    names = {r.id: r.name for r in conn.execute(sa.select(tools.c.id, tools.c.name))}
    _swap(conn, names)
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("tools") as batch:
            batch.create_unique_constraint("uq_tools_name", ["name"])
    else:
        op.create_unique_constraint("tools_name_key", "tools", ["name"])
