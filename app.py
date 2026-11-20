"""Recipe Box API — a Flask + SQLite CRUD API for recipes.

Recipes live in SQLite, passwords are hashed with Argon2, and login returns a
one-hour JWT. A user can edit or delete only their own recipes.

Tables (created by init_db.py, migrated by ensure_schema() below):

    users                   one row per account; is_admin marks the curator
    recipes                 one row per recipe; is_public = 0 hides a draft
    profiles                display name and bio, shown on the dashboard
    recipe_change_requests  suggestions other cooks make about a recipe
    user_notifications      messages the dashboard shows once

ensure_schema() runs at import time and adds the columns and tables that older
recipes.db files are missing, so the app still opens a database created before
those features existed.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Flask, g, jsonify, redirect, render_template, request, url_for

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "development-secret-change-me-use-JWT_SECRET-in-production",
)

DATABASE = "recipes.db"
ph = PasswordHasher()
app = Flask(__name__)


def ensure_schema():
    """Add the columns and tables that newer features need.

    SQLite's ALTER TABLE cannot add a column twice, so each change is guarded by
    a PRAGMA table_info check. This is the whole migration system: no framework,
    and an old recipes.db keeps working.
    """
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    cols = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    if "is_admin" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

    cols = {row[1] for row in db.execute("PRAGMA table_info(recipes)")}
    if "is_public" not in cols:
        db.execute("ALTER TABLE recipes ADD COLUMN is_public INTEGER NOT NULL DEFAULT 1")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            display_name TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            location TEXT DEFAULT '',
            website TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS recipe_change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            requester_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            FOREIGN KEY(requester_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    db.commit()
    db.close()


ensure_schema()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def recipe_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "ingredients": row["ingredients"],
        "instructions": row["instructions"],
        "is_public": bool(row["is_public"]),
    }


def get_authenticated_user_id():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Missing or Invalid Token"}), 401)

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"]), None
    except (jwt.ExpiredSignatureError, jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None, (jsonify({"error": "Invalid token"}), 401)


def current_user():
    user_id, error = get_authenticated_user_id()
    if error:
        return None, error

    row = get_db().execute(
        "SELECT id, username, email, is_admin FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None, (jsonify({"error": "Invalid token"}), 401)
    return row, None


def require_admin():
    user, error = current_user()
    if error:
        return None, error
    if not user["is_admin"]:
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


def notify_user(user_id, message):
    if user_id is not None:
        get_db().execute(
            "INSERT INTO user_notifications(user_id,message) VALUES(?,?)",
            (user_id, message),
        )


def owns_or_admin(recipe, data):
    user, error = current_user()
    if error:
        return False, error
    if recipe["user_id"] == user["id"]:
        return True, None

    data = data or {}
    admin_name = data.get("admin_username", "")
    admin_password = data.get("admin_password", "")
    admin = get_db().execute(
        "SELECT * FROM users WHERE username=? AND is_admin=1",
        (admin_name,),
    ).fetchone()
    if admin and admin_password:
        try:
            ph.verify(admin["password_hash"], admin_password)
            return True, None
        except VerifyMismatchError:
            pass

    return False, (
        jsonify(
            {
                "error": "Only the recipe owner can make changes. "
                "Admin approval credentials are required to override."
            }
        ),
        403,
    )


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------


@app.get("/")
def home():
    return render_template("welcome.html")


@app.get("/login")
def login_page():
    return render_template("login.html")


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.get("/guest")
def guest_page():
    return render_template("guest.html")


@app.get("/profile")
def profile_page():
    return render_template("profile.html")


@app.get("/owner/requests")
def owner_requests_page():
    return render_template("owner_requests.html")


@app.get("/admin")
def admin_page():
    return render_template("admin.html")


@app.get("/recipe/new")
def new_recipe_page():
    return render_template("recipe_form.html", recipe_id=None)


@app.get("/recipe/<int:recipe_id>")
def edit_recipe_page(recipe_id):
    return render_template("recipe_form.html", recipe_id=recipe_id)


@app.get("/register")
def register_page():
    return render_template("register.html")


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------


@app.post("/users")
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    missing_fields = []
    if not username:
        missing_fields.append("username")
    if not email:
        missing_fields.append("email")
    if not password:
        missing_fields.append("password")

    if missing_fields:
        return jsonify({"error": "Missing Required Fields", "fields": missing_fields}), 400

    db = get_db()
    try:
        hashed_password = ph.hash(password)

        db.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (
                username,
                email,
                hashed_password,
                int(username == os.getenv("ADMIN_USERNAME")),
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or Email already in use"}), 409

    return jsonify({"username": username, "email": email}), 201


@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

    missing_fields = []
    if not username:
        missing_fields.append("username")
    if not password:
        missing_fields.append("password")

    if missing_fields:
        return jsonify({"error": "Missing Required Fields", "fields": missing_fields}), 400

    row = get_db().execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if row is None:
        return jsonify({"error": "Bad Credentials"}), 401

    if row["locked_until"]:
        locked_until = datetime.fromisoformat(row["locked_until"])

        if datetime.utcnow() < locked_until:
            return (
                jsonify(
                    {
                        "error": "account locked, try again later",
                        "message": "Too Many Failed login Attempts. Try Again Later.",
                    }
                ),
                423,
            )

        get_db().execute(
            """
            UPDATE users
            SET failed_logins = 0,
                locked_until = NULL
            WHERE id = ?
            """,
            (row["id"],),
        )
        get_db().commit()

    try:
        ph.verify(row["password_hash"], password)
        get_db().execute(
            """
            UPDATE users
            SET failed_logins = 0,
                locked_until = NULL
            WHERE id = ?
            """,
            (row["id"],),
        )
        get_db().commit()

        user_id = row["id"]
        payload = {
            "sub": str(user_id),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        return (
            jsonify(
                {
                    "token": token,
                    "id": row["id"],
                    "username": row["username"],
                    "is_admin": bool(row["is_admin"]),
                }
            ),
            200,
        )

    except VerifyMismatchError:
        failed = row["failed_logins"] + 1

        if failed >= 3:
            lock_until = datetime.utcnow() + timedelta(minutes=5)

            get_db().execute(
                """
                UPDATE users
                SET failed_logins = ?,
                    locked_until = ?
                WHERE id = ?
                """,
                (failed, lock_until.isoformat(), row["id"]),
            )
            get_db().commit()

            return (
                jsonify(
                    {
                        "error": "Account Locked",
                        "message": "Too many failed login attempts.",
                        "try_again_after": lock_until.isoformat(),
                    }
                ),
                423,
            )

        get_db().execute(
            """
            UPDATE users
            SET failed_logins = ?
            WHERE id = ?
            """,
            (failed, row["id"]),
        )
        get_db().commit()

        return (
            jsonify(
                {
                    "error": "Bad Credentials",
                    "message": "Username or Password is incorrect.",
                }
            ),
            401,
        )


@app.get("/me")
def me():
    user, error = current_user()
    if error:
        return error
    return jsonify(dict(user))


@app.route("/profile/data", methods=["GET", "PUT"])
def profile_data():
    user, error = current_user()
    if error:
        return error

    db = get_db()

    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        db.execute(
            """
            INSERT INTO profiles(user_id, display_name, bio, location, website)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                bio = excluded.bio,
                location = excluded.location,
                website = excluded.website
            """,
            (
                user["id"],
                data.get("display_name", ""),
                data.get("bio", ""),
                data.get("location", ""),
                data.get("website", ""),
            ),
        )
        db.commit()

    row = db.execute(
        """
        SELECT p.*, u.username, u.email
        FROM users u
        LEFT JOIN profiles p ON p.user_id = u.id
        WHERE u.id = ?
        """,
        (user["id"],),
    ).fetchone()
    return jsonify(dict(row))


@app.get("/notifications")
def notifications():
    user, error = current_user()
    if error:
        return error

    db = get_db()
    rows = db.execute(
        """
        SELECT id, message, created_at
        FROM user_notifications
        WHERE user_id = ? AND is_read = 0
        ORDER BY id DESC
        """,
        (user["id"],),
    ).fetchall()

    db.execute("UPDATE user_notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
    db.commit()

    return jsonify([dict(r) for r in rows])


# --------------------------------------------------------------------------
# Recipes
# --------------------------------------------------------------------------


@app.get("/recipes")
def list_recipes():
    user, error = current_user()
    if error:
        return error

    rows = get_db().execute("SELECT * FROM recipes ORDER BY id").fetchall()
    return jsonify([recipe_to_dict(r) for r in rows])


@app.get("/recipes/public")
def list_public_recipes():
    rows = get_db().execute(
        "SELECT * FROM recipes WHERE is_public = 1 ORDER BY id"
    ).fetchall()
    return jsonify([recipe_to_dict(r) for r in rows])


@app.get("/recipes/<int:recipe_id>")
def get_recipe(recipe_id):
    row = get_db().execute(
        "SELECT * FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()

    if row is None:
        return jsonify({"error": "Recipe not Found"}), 404

    if not row["is_public"]:
        user_id, error = get_authenticated_user_id()
        if error:
            return error
        if row["user_id"] != user_id:
            return jsonify({"error": "Recipe not Found"}), 404

    return jsonify(recipe_to_dict(row))


@app.post("/recipes")
def create_recipe():
    user_id, error = get_authenticated_user_id()
    if error:
        return error

    data = request.get_json(silent=True)

    if not data or not data.get("title") or not data.get("ingredients"):
        return jsonify({"error": "Title and Ingredients are Required"}), 400

    db = get_db()
    try:
        cur = db.execute(
            """
            INSERT INTO recipes (title, ingredients, instructions, is_public, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data["title"],
                data["ingredients"],
                data.get("instructions", ""),
                1 if data.get("is_public", True) else 0,
                user_id,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "The Recipe with that Title already exists"}), 409

    row = db.execute("SELECT * FROM recipes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(recipe_to_dict(row)), 201


@app.patch("/recipes/<int:recipe_id>")
def update_recipe(recipe_id):
    user_id, error = get_authenticated_user_id()
    if error:
        return error

    db = get_db()
    recipe = db.execute(
        "SELECT * FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()

    if recipe is None:
        return jsonify({"error": "Recipe not Found"}), 404

    data = request.get_json(silent=True)

    allowed, error = owns_or_admin(recipe, data)
    if not allowed:
        return error

    if not data:
        return jsonify({"error": "a JSON body is required"}), 400

    fields, values = [], []

    for column in ("title", "ingredients", "instructions"):
        if column in data:
            fields.append(f"{column} = ?")
            values.append(data[column])

    if "is_public" in data:
        fields.append("is_public = ?")
        values.append(1 if data["is_public"] else 0)

    if not fields:
        return jsonify({"error": "Nothing to Update"}), 400

    values.append(recipe_id)

    try:
        cur = db.execute(
            f"UPDATE recipes SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "A Recipe with that Title already exists"}), 409

    if cur.rowcount == 0:
        return jsonify({"error": "Recipe not found"}), 404

    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    return jsonify(recipe_to_dict(row))


@app.delete("/recipes/<int:recipe_id>")
def delete_recipe(recipe_id):
    user_id, error = get_authenticated_user_id()
    if error:
        return error

    db = get_db()
    recipe = db.execute(
        "SELECT * FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()

    if recipe is None:
        return jsonify({"error": "Recipe not found"}), 404

    allowed, error = owns_or_admin(recipe, request.get_json(silent=True))
    if not allowed:
        return error

    db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    db.commit()

    return jsonify({"message": "Recipe Deleted"}), 200


# --------------------------------------------------------------------------
# Suggestions and approvals
# --------------------------------------------------------------------------


@app.post("/recipes/<int:recipe_id>/approval-requests")
def request_recipe_approval(recipe_id):
    user, error = current_user()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    action = data.get("action")

    if action not in ("edit", "delete"):
        return jsonify({"error": "Action must be edit or delete"}), 400

    db = get_db()
    recipe = db.execute(
        "SELECT id, user_id FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()

    if recipe is None:
        return jsonify({"error": "Recipe not found"}), 404

    if recipe["user_id"] == user["id"]:
        return jsonify({"error": "You own this recipe; make the change directly."}), 400

    payload = data.get("payload", {}) if action == "edit" else {}

    cur = db.execute(
        """
        INSERT INTO recipe_change_requests(recipe_id, requester_id, action, payload)
        VALUES (?, ?, ?, ?)
        """,
        (recipe_id, user["id"], action, json.dumps(payload)),
    )
    db.commit()

    return (
        jsonify(
            {
                "message": "Approval request sent to an admin.",
                "request_id": cur.lastrowid,
            }
        ),
        202,
    )


@app.get("/owner/approval-requests")
def owner_approval_requests():
    user, error = current_user()
    if error:
        return error

    rows = get_db().execute(
        """
        SELECT q.id, q.recipe_id, q.requester_id, q.action, q.payload, q.created_at,
               u.username AS requester, r.title AS recipe_title
        FROM recipe_change_requests q
        JOIN users u ON u.id = q.requester_id
        JOIN recipes r ON r.id = q.recipe_id
        WHERE q.status = 'pending' AND r.user_id = ?
        ORDER BY q.created_at
        """,
        (user["id"],),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/owner/approval-requests/<int:request_id>")
def owner_decide_request(request_id):
    user, error = current_user()
    if error:
        return error

    decision = (request.get_json(silent=True) or {}).get("decision")
    if decision not in ("approve", "reject"):
        return jsonify({"error": "Decision must be approve or reject"}), 400

    db = get_db()
    req = db.execute(
        """
        SELECT q.*, r.user_id
        FROM recipe_change_requests q
        JOIN recipes r ON r.id = q.recipe_id
        WHERE q.id = ? AND q.status = 'pending' AND r.user_id = ?
        """,
        (request_id, user["id"]),
    ).fetchone()

    if not req:
        return jsonify({"error": "Pending request not found for one of your recipes"}), 404

    if decision == "approve":
        if req["action"] == "delete":
            db.execute("DELETE FROM recipes WHERE id = ?", (req["recipe_id"],))
        else:
            fields = {
                k: v
                for k, v in json.loads(req["payload"] or "{}").items()
                if k in ("title", "ingredients", "instructions", "is_public")
            }
            if not fields:
                return jsonify({"error": "Edit request contains no recipe changes"}), 400

            sql = ", ".join(f"{k} = ?" for k in fields)
            vals = [int(bool(v)) if k == "is_public" else v for k, v in fields.items()]
            try:
                db.execute(
                    f"UPDATE recipes SET {sql} WHERE id = ?",
                    (*vals, req["recipe_id"]),
                )
            except sqlite3.IntegrityError:
                return jsonify({"error": "Duplicate recipe title"}), 409

    db.execute(
        "UPDATE recipe_change_requests SET status = ? WHERE id = ?",
        ("owner_approved" if decision == "approve" else "owner_rejected", request_id),
    )
    db.commit()

    return jsonify({"message": f"Request {decision}d by you"})


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------


@app.get("/admin/users")
def admin_users():
    _, error = require_admin()
    if error:
        return error

    rows = get_db().execute(
        """
        SELECT u.id, u.username, u.email, u.is_admin,
               p.display_name, p.bio, p.location, p.website, p.notes
        FROM users u
        LEFT JOIN profiles p ON p.user_id = u.id
        ORDER BY u.id
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.put("/admin/users/<int:user_id>/profile")
def admin_profile(user_id):
    _, error = require_admin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    db = get_db()

    if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
        return jsonify({"error": "User not found"}), 404

    db.execute(
        """
        INSERT INTO profiles(user_id, display_name, bio, location, website, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            bio = excluded.bio,
            location = excluded.location,
            website = excluded.website,
            notes = excluded.notes
        """,
        (
            user_id,
            data.get("display_name", ""),
            data.get("bio", ""),
            data.get("location", ""),
            data.get("website", ""),
            data.get("notes", ""),
        ),
    )
    db.commit()
    return jsonify({"message": "Profile updated"})


@app.post("/admin/users")
def admin_add_user():
    _, error = require_admin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    if not all(data.get(k) for k in ("username", "email", "password")):
        return jsonify({"error": "Username, email and password are required"}), 400

    try:
        cur = get_db().execute(
            "INSERT INTO users(username, email, password_hash, is_admin) VALUES(?, ?, ?, ?)",
            (
                data["username"],
                data["email"],
                ph.hash(data["password"]),
                int(bool(data.get("is_admin"))),
            ),
        )
        get_db().commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already in use"}), 409

    return jsonify({"id": cur.lastrowid, "username": data["username"]}), 201


@app.delete("/admin/users/<int:user_id>")
def admin_remove_user(user_id):
    _, error = require_admin()
    if error:
        return error

    db = get_db()
    db.execute("UPDATE recipes SET user_id = NULL WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"message": "User removed"})


@app.get("/admin/recipes")
def admin_recipes():
    _, error = require_admin()
    if error:
        return error

    rows = get_db().execute("SELECT * FROM recipes ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/admin/recipes")
def admin_create_recipe():
    _, error = require_admin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("ingredients"):
        return jsonify({"error": "Title and ingredients are required"}), 400

    cur = get_db().execute(
        """
        INSERT INTO recipes(title, ingredients, instructions, is_public, user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["title"],
            data["ingredients"],
            data.get("instructions", ""),
            int(bool(data.get("is_public", True))),
            data.get("user_id"),
        ),
    )
    get_db().commit()
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/admin/recipes/<int:recipe_id>", methods=["PUT", "DELETE"])
def admin_recipe(recipe_id):
    admin, error = require_admin()
    if error:
        return error

    db = get_db()
    existing = db.execute(
        "SELECT title, user_id FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()

    if not existing:
        return jsonify({"error": "Recipe not found"}), 404

    if request.method == "DELETE":
        notify_user(
            existing["user_id"],
            f'Admin {admin["username"]} deleted your recipe “{existing["title"]}”.',
        )
        db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        db.commit()
        return jsonify({"message": "Recipe removed"})

    data = request.get_json(silent=True) or {}

    try:
        db.execute(
            """
            UPDATE recipes
            SET title = ?, ingredients = ?, instructions = ?, is_public = ?, user_id = ?
            WHERE id = ?
            """,
            (
                data.get("title", ""),
                data.get("ingredients", ""),
                data.get("instructions", ""),
                int(bool(data.get("is_public"))),
                data.get("user_id"),
                recipe_id,
            ),
        )

        if existing["user_id"] is not None:
            notify_user(
                existing["user_id"],
                f'Admin {admin["username"]} changed your recipe “{existing["title"]}”.',
            )

        if data.get("user_id") is not None and data.get("user_id") != existing["user_id"]:
            notify_user(
                data.get("user_id"),
                f'Admin {admin["username"]} assigned recipe '
                f'“{data.get("title", existing["title"])}” to you.',
            )

        db.commit()
        return jsonify({"message": "Recipe updated"})

    except sqlite3.IntegrityError:
        return jsonify({"error": "Invalid owner or duplicate title"}), 400


@app.get("/admin/approval-requests")
def admin_approval_requests():
    _, error = require_admin()
    if error:
        return error

    rows = get_db().execute(
        """
        SELECT q.id, q.recipe_id, q.requester_id, q.action, q.payload, q.created_at,
               u.username AS requester, r.title AS recipe_title
        FROM recipe_change_requests q
        JOIN users u ON u.id = q.requester_id
        JOIN recipes r ON r.id = q.recipe_id
        WHERE q.status = 'pending'
        ORDER BY q.created_at
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/admin/approval-requests/<int:request_id>")
def decide_approval_request(request_id):
    admin, error = require_admin()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    decision = data.get("decision")

    if decision not in ("approve", "reject"):
        return jsonify({"error": "Decision must be approve or reject"}), 400

    db = get_db()
    req = db.execute(
        "SELECT * FROM recipe_change_requests WHERE id = ? AND status = 'pending'",
        (request_id,),
    ).fetchone()

    if not req:
        return jsonify({"error": "Pending request not found"}), 404

    if decision == "approve":
        owner = db.execute(
            "SELECT user_id, title FROM recipes WHERE id = ?",
            (req["recipe_id"],),
        ).fetchone()

        if owner and owner["user_id"] is not None:
            notify_user(
                owner["user_id"],
                f'Admin {admin["username"]} approved a {req["action"]} request '
                f'for your recipe “{owner["title"]}”.',
            )

        if req["action"] == "delete":
            db.execute("DELETE FROM recipes WHERE id = ?", (req["recipe_id"],))
        else:
            payload = json.loads(req["payload"] or "{}")
            fields = {
                k: payload[k]
                for k in ("title", "ingredients", "instructions", "is_public")
                if k in payload
            }
            allowed = {"title", "ingredients", "instructions", "is_public"}
            if not fields:
                return jsonify({"error": "Edit request contains no recipe changes"}), 400

            assignments = ", ".join(f"{key} = ?" for key in fields)
            values = [
                int(bool(v)) if key == "is_public" else v for key, v in fields.items()
            ]
            try:
                db.execute(
                    f"UPDATE recipes SET {assignments} WHERE id = ?",
                    (*values, req["recipe_id"]),
                )
            except sqlite3.IntegrityError:
                return jsonify({"error": "Approval would create a duplicate recipe title"}), 409

    db.execute(
        "UPDATE recipe_change_requests SET status = ? WHERE id = ?",
        ("approved" if decision == "approve" else "rejected", request_id),
    )
    db.commit()

    return jsonify({"message": f"Request {decision}d", "admin": admin["username"]})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
