"""Create and seed recipes.db.

Usage:
    python init_db.py            # create any missing tables, seed if the recipes table is empty
    python init_db.py --reset    # delete recipes.db and rebuild it from scratch

This script only shapes *fresh* databases. `CREATE TABLE IF NOT EXISTS` never
touches a table that already exists, so editing the SCHEMA below has no effect
on an existing recipes.db -- that is what --reset is for. app.py's
ensure_schema() still migrates old files when it opens them; the two are meant
to agree, not to replace each other.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Resolved next to this file so running the script from another directory does
# not quietly create a second, empty database there.
DB_PATH = Path(__file__).with_name("recipes.db")

# Keep this in sync with ensure_schema() in app.py. Anything the app queries
# has to exist after a fresh install, or the first request fails at runtime.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    ingredients TEXT NOT NULL,
    instructions TEXT NOT NULL DEFAULT '',
    is_public INTEGER NOT NULL DEFAULT 1,
    -- Nullable on purpose: admin_remove_user() keeps recipes and clears the
    -- owner, and older seed rows have no owner at all.
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY,
    display_name TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    location TEXT DEFAULT '',
    website TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recipe_change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    requester_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- The inbox queries filter on exactly these columns, and SQLite has no other
-- reason to keep them around.
CREATE INDEX IF NOT EXISTS idx_requests_recipe_status
    ON recipe_change_requests(recipe_id, status);
CREATE INDEX IF NOT EXISTS idx_requests_requester
    ON recipe_change_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON user_notifications(user_id, is_read);
"""

# (title, ingredients, instructions, is_public, user_id)
# user_id is NULL: these are demo rows with no owner, so nobody can edit them
# until an admin assigns one. That is deliberate -- see F5 in WORKFLOW.md.
SEED = [
    (
        "Shakshuka",
        "eggs, tomatoes, peppers, onion, cumin, paprika",
        "Simmer the sauce, crack in the eggs, cover until just set.",
        1,
        None,
    ),
    (
        "Overnight oats",
        "rolled oats, milk, yogurt, chia seeds, honey",
        "Stir everything together and refrigerate overnight.",
        1,
        None,
    ),
    (
        "Secret family hot sauce",
        "habaneros, garlic, vinegar, a secret ingredient",
        "If we wrote it down here, it wouldn't be a secret.",
        0,
        None,
    ),
]


def reset_database():
    """Delete the database and SQLite's sidecar files, if they exist."""
    sidecars = [DB_PATH, Path(str(DB_PATH) + "-wal"), Path(str(DB_PATH) + "-shm")]
    for path in sidecars:
        if path.exists():
            path.unlink()
            print(f"Removed {path.name}")


def warn_about_drift(connection):
    """A pre-existing table keeps its old columns; say so instead of failing later."""
    expected = {
        "users": ("is_admin",),
        "recipes": ("is_public",),
    }
    stale = []
    for table, columns in expected.items():
        present = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        stale.extend(f"{table}.{column}" for column in columns if column not in present)
    if stale:
        print(
            "Note: this database predates "
            + ", ".join(stale)
            + ".\n"
            "      app.py's ensure_schema() will add the column when it opens the file,\n"
            "      but --reset gives you a database that matches this script exactly.",
            file=sys.stderr,
        )


def create_schema(connection):
    connection.executescript(SCHEMA)


def seed(connection):
    existing = connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    if existing:
        print(f"recipes table already has {existing} rows - not seeding.")
        return
    connection.executemany(
        "INSERT INTO recipes (title, ingredients, instructions, is_public, user_id)"
        " VALUES (?, ?, ?, ?, ?)",
        SEED,
    )
    connection.commit()
    print(f"Seeded {len(SEED)} demo recipes.")


def main():
    parser = argparse.ArgumentParser(description="Create and seed recipes.db.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the existing database first, then rebuild it from scratch",
    )
    args = parser.parse_args()

    if args.reset:
        reset_database()

    fresh = not DB_PATH.exists()

    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        create_schema(connection)
        if not fresh:
            warn_about_drift(connection)
        seed(connection)

        users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        recipes = connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    finally:
        connection.close()

    print(f"Database ready at {DB_PATH.resolve()}")
    print(f"  users:   {users}")
    print(f"  recipes: {recipes}")


if __name__ == "__main__":
    main()
