# Litestar Skill

[![CI](https://github.com/Bjern/litestar-user-cookiecutter/actions/workflows/ci.yml/badge.svg)](https://github.com/Bjern/litestar-user-cookiecutter/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![Litestar](https://img.shields.io/badge/litestar-2.x-purple)

A Litestar web API with built-in user authentication and management, powered by [litestar-users](https://github.com/mvbosch/litestar-users).

## Tech Stack

- **Framework**: [Litestar](https://litestar.dev/) 2.x
- **Auth**: Session-based authentication via litestar-users
- **Database**: SQLite with aiosqlite (async)
- **ORM**: SQLAlchemy via Advanced Alchemy
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Config**: pydantic-settings (`.env` file)
- **Logging**: loguru (structured, rotated, with sensitive field redaction)
- **Testing**: pytest + Litestar TestClient
- **Linting**: ruff, mypy

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

### Install

```bash
uv sync
```

### Environment

Create a `.env` file in the project root:

```env
ENCODING_SECRET=your-32-character-secret-here!!
AUTO_VERIFY_USERS=true
DATABASE_URL=sqlite+aiosqlite:///db.sqlite3
APP_TITLE="My App"
LOG_LEVEL=INFO
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENCODING_SECRET` | Yes | — | Secret key for session/JWT encoding (must be exactly 16, 24, or 32 characters) |
| `AUTO_VERIFY_USERS` | No | `false` | Auto-verify users on registration (enable for dev) |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///db.sqlite3` | Async database URL (e.g. `postgresql+asyncpg://user:pass@localhost/db`) |
| `APP_TITLE` | No | `Litestar API` | Application title in OpenAPI docs |
| `LOG_LEVEL` | No | `INFO` | Log level (`TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

### Database

Run migrations to create the database:

```bash
uv run alembic upgrade head
```

To generate a new migration after changing models:

```bash
uv run alembic revision --autogenerate -m "description of change"
```

### Run

```bash
uv run litestar run --reload
```

The API will be available at `http://localhost:8000`. OpenAPI docs are at `/schema/swagger`.

## Project Structure

```
app/
├── main.py                  # Litestar app entry point
├── domain/                  # Domain logic by bounded context
│   ├── default/
│   │   ├── routes.py        # Health check endpoint
│   │   └── schemas.py       # Health response schema
│   └── users/
│       ├── models.py        # SQLAlchemy User model
│       ├── schemas.py       # DTOs (registration, read, update)
│       └── services.py      # UserService with token delivery hooks
├── lib/                     # Shared infrastructure
│   ├── db.py                # Database plugin config
│   ├── logging.py           # loguru setup, redaction, stdlib intercept
│   ├── settings.py          # Environment settings (singleton via get_settings)
│   └── security.py          # Auth plugin config
tests/
├── conftest.py              # Test fixtures (in-memory DB, authenticated_client)
└── test_users.py            # User flow tests (19 tests)
alembic/                     # Database migrations
```

## API Endpoints

Routes are tagged in Swagger UI for easy navigation.

### Auth

| Method | Path        | Auth Required | Description              |
|--------|-------------|---------------|--------------------------|
| POST   | `/register` | No            | Register a new user      |
| POST   | `/login`    | No            | Log in (creates session) |
| POST   | `/logout`   | Yes           | Log out (ends session)   |
| POST   | `/verify`   | No            | Verify user account (requires token) |
| POST   | `/forgot-password` | No     | Request a password reset token |
| POST   | `/reset-password`  | No     | Reset password (requires token) |

### Users

| Method | Path         | Auth Required | Description              |
|--------|--------------|---------------|--------------------------|
| GET    | `/users/me`  | Yes           | Get current user profile |
| PATCH  | `/users/me`  | Yes           | Update current user      |

### General

| Method | Path        | Auth Required | Description              |
|--------|-------------|---------------|--------------------------|
| GET    | `/health`   | No            | Health check             |

> **Note:** litestar-users requires users to be both `is_active` and `is_verified` to authenticate. Set `AUTO_VERIFY_USERS=true` in `.env` to skip verification during development.

> **Token delivery:** The `/verify` and `/forgot-password` flows generate JWT tokens that must be delivered to the user (e.g. via email). The `send_verification_token` and `send_password_reset_token` methods in `app/domain/users/services.py` are placeholders that log tokens to the console. Replace them with actual delivery logic for production.

## User Flows

### Registration

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Litestar App
    participant S as UserService
    participant DB as SQLite

    C->>A: POST /register {email, password}
    A->>S: register(data)
    S->>S: Hash password
    S->>DB: INSERT user
    DB-->>S: User created
    S->>S: post_registration_hook()
    alt AUTO_VERIFY_USERS=true
        S->>DB: SET is_verified=true
    else AUTO_VERIFY_USERS=false (default)
        S->>S: initiate_verification() → see Verification flow
    end
    S-->>A: User object
    A-->>C: 201 {id, email, is_active, is_verified}
```

### Verification

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Litestar App
    participant S as UserService
    participant E as Email/SMS (TODO)

    Note over C,E: During registration:
    S->>S: generate_token(user_id, aud="verify")
    S->>E: send_verification_token(user, token)
    E-->>C: Deliver token (email link, SMS, etc.)

    Note over C,E: User verifies:
    C->>A: POST /verify {token}
    A->>S: verify(token)
    S->>S: Decode & validate JWT
    S->>S: SET is_verified=true
    S-->>A: Verified user
    A-->>C: 201 User data
```

### Password Reset

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Litestar App
    participant S as UserService
    participant E as Email/SMS (TODO)
    participant DB as SQLite

    C->>A: POST /forgot-password {email}
    A->>S: initiate_password_reset(email)
    S->>DB: Look up user by email
    alt User exists
        S->>S: generate_token(user_id, aud="reset_password")
        S->>E: send_password_reset_token(user, token)
        E-->>C: Deliver token
    end
    A-->>C: 200 (always, to prevent email enumeration)

    Note over C,E: User resets password:
    C->>A: POST /reset-password {token, password}
    A->>S: reset_password(token, password)
    S->>S: Decode & validate JWT
    S->>S: Hash new password
    S->>DB: UPDATE password_hash
    S-->>A: Success
    A-->>C: 200
```

### Login

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Litestar App
    participant S as UserService
    participant DB as SQLite
    participant Sess as Session Store

    C->>A: POST /login {email, password}
    A->>S: authenticate(email, password)
    S->>DB: SELECT user WHERE email
    DB-->>S: User record
    S->>S: Verify password hash
    S-->>A: Authenticated user
    A->>Sess: Create session
    Sess-->>A: Session ID
    A-->>C: 201 User data + Set-Cookie (session)
```

### Authenticated Request (e.g. GET /users/me)

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as Session Middleware
    participant A as Litestar App
    participant Sess as Session Store
    participant DB as SQLite

    C->>MW: Request + session cookie
    MW->>Sess: Look up session
    Sess-->>MW: user_id
    MW->>DB: SELECT user WHERE id AND is_active AND is_verified
    DB-->>MW: User record
    MW->>A: request.user = User
    A-->>C: 200 Response

    Note over C,MW: Without valid session cookie:
    C->>MW: Request (no cookie)
    MW-->>C: 401 Unauthorized
```

### Logout

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Litestar App
    participant Sess as Session Store

    C->>A: POST /logout + session cookie
    A->>Sess: Delete session
    Sess-->>A: Session removed
    A-->>C: 201 + Clear-Cookie
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test
uv run pytest tests/ -k test_login_success
```

Tests use an in-memory SQLite database with auto-created tables, so they are fully isolated and don't touch the development database.

## Linting & Type Checking

```bash
uv run ruff check .
uv run mypy app/
```
