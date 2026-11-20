# My Recipe Box API

A Flask and SQLite recipe-sharing application. Users can browse public recipes, create and manage their own recipes, maintain a profile, and submit recipe changes for approval. Administrators can manage users, recipes, and approval requests.

## Features

- Guest browsing of public recipes
- User registration and JWT-based login
- Password hashing with Argon2
- One-hour access tokens
- Account lockout after repeated failed logins
- Create, update, and delete recipes owned by the authenticated user
- Public and private recipe visibility
- User profiles and notifications
- Recipe change requests and owner/admin approval workflows
- Admin user and recipe management
- SQLite database initialization and demo seed data

## Requirements

- Python 3.9 or newer
- `pip`

## Getting started

1. Clone the repository and enter the project directory:

   ```bash
   git clone https://github.com/GrantRuffner16301/my-recipe-box-api.git
   cd my-recipe-box-api
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables. At minimum, set a strong production JWT secret:

   ```bash
   export JWT_SECRET="replace-with-a-long-random-secret"
   ```

   On Windows PowerShell:

   ```powershell
   $env:JWT_SECRET = "replace-with-a-long-random-secret"
   ```

   `ADMIN_USERNAME` may be set to identify the username that receives admin privileges when registered.

5. Create and seed the database:

   ```bash
   python init_db.py
   ```

6. Start the application:

   ```bash
   python app.py
   ```

The application runs at <http://localhost:5001>. The database is stored in `recipes.db`, which is intentionally ignored by Git.

To rebuild the local database and restore the demo recipes:

```bash
python init_db.py --reset
```

## Authentication

Register with `POST /users`, then log in with `POST /login`. The login response includes a JWT token valid for one hour. Send it on protected requests using:

```http
Authorization: Bearer <token>
```

Keep `JWT_SECRET` private and change it from the development fallback before deploying the application.

## API overview

### Public endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `GET` | `/recipes/public` | List public recipes |
| `GET` | `/recipes/<id>` | Get a public recipe |
| `POST` | `/users` | Register a user |
| `POST` | `/login` | Authenticate and receive a JWT |

### Authenticated endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/me` | Get the current user |
| `GET` | `/recipes` | List recipes |
| `POST` | `/recipes` | Create a recipe |
| `PATCH` | `/recipes/<id>` | Update an owned recipe |
| `DELETE` | `/recipes/<id>` | Delete an owned recipe |
| `GET` | `/profile/data` | Get the current profile |
| `PUT` | `/profile/data` | Update the current profile |
| `GET` | `/notifications` | List notifications |
| `POST` | `/recipes/<id>/approval-requests` | Submit a recipe change request |
| `GET` | `/owner/approval-requests` | List owner approval requests |
| `POST` | `/owner/approval-requests/<id>` | Approve or reject an owner request |

### Admin endpoints

Admin access is required for these routes:

- `GET /admin/users`
- `POST /admin/users`
- `PUT /admin/users/<id>/profile`
- `DELETE /admin/users/<id>`
- `GET /admin/recipes`
- `POST /admin/recipes`
- `PUT /admin/recipes/<id>`
- `DELETE /admin/recipes/<id>`
- `GET /admin/approval-requests`
- `POST /admin/approval-requests/<id>`

## Example requests

Register a user:

```bash
curl -X POST http://localhost:5001/users \\
  -H 'Content-Type: application/json' \\
  -d '{"username":"sam","email":"sam@example.com","password":"change-me"}'
```

Log in and save the token:

```bash
TOKEN=$(curl -s -X POST http://localhost:5001/login \\
  -H 'Content-Type: application/json' \\
  -d '{"username":"sam","password":"change-me"}' | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
```

Create a public recipe:

```bash
curl -X POST http://localhost:5001/recipes \\
  -H "Authorization: Bearer $TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"title":"Pasta primavera","ingredients":"pasta, vegetables, olive oil","instructions":"Cook and combine.","is_public":true}'
```

## Project layout

```text
app.py             Flask routes, authentication, and application logic
init_db.py         Database schema creation and demo seed data
requirements.txt   Python dependencies
templates/         HTML pages
static/            Browser-side JavaScript and CSS
```

## Notes

- Recipe titles are unique.
- Private recipes are only available to their owner or an administrator.
- The development server starts with Flask debug mode enabled; use a production WSGI server for deployment.
