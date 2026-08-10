import contextlib
import sqlite3

for db in ["jobcopilot.db", "test_migration.db"]:
    conn = sqlite3.connect(db)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    version = None
    with contextlib.suppress(sqlite3.OperationalError):
        version = list(conn.execute("SELECT * FROM alembic_version"))
    print(f"=== {db} ===")
    print("tables:", sorted(tables))
    print("alembic_version:", version)
    conn.close()
