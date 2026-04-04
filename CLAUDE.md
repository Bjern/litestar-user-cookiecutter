# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Litestar web API with user authentication and management via `litestar-users`. Uses SQLite (aiosqlite) for storage, Alembic for migrations, Pydantic v2 for validation, and Advanced Alchemy for database models/DTOs. Configuration is loaded from `.env` via pydantic-settings.

- **Python**: 3.13
- **Package manager**: uv
- **Framework**: Litestar 2.x with standard extras
- **Auth**: Session-based (ServerSideSessionConfig) via litestar-users

## Commands

```bash
# Install dependencies
uv sync

# Run dev server
uv run litestar run --debug

# Run with reload
uv run litestar run --reload

# Run all tests
uv run pytest tests/ -v

# Run a single test
uv run pytest tests/ -k test_register

# Lint
uv run ruff check .

# Type check
uv run mypy app/

# Generate a migration after model changes
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

## Architecture

```
app/
  main.py              — Litestar app instance, route handlers, plugin wiring
  lib/
    db.py              — SQLAlchemyAsyncConfig + SQLAlchemyInitPlugin (sqlite+aiosqlite)
    settings.py        — pydantic-settings Settings class, reads from .env
    security.py        — LitestarUsersPlugin config (session auth, handler configs)
  domain/
    users/
      models.py        — User model (UUIDBase + SQLAlchemyUserMixin)
      schemas.py       — DTOs: UserRegistrationDTO, UserReadDTO, UserUpdateDTO
      services.py      — UserService (extends BaseUserService, token delivery overrides)
alembic/
  env.py               — Alembic env importing UUIDBase metadata + all models
  versions/            — Migration scripts
tests/
  conftest.py          — Test fixtures: in-memory SQLite app per test
  test_users.py        — User flow tests (register, login, logout, duplicate, auth)
```

Domain code is organized under `app/domain/` by bounded context. Shared infra lives in `app/lib/`.

## Key Patterns

- **DB plugin**: `SQLAlchemyInitPlugin` with `before_send_handler="autocommit"` — required by litestar-users for atomic request transactions.
- **Migrations**: Alembic uses sync `sqlite:///` URL (in `alembic.ini`), while the app uses async `sqlite+aiosqlite:///`. Migration scripts need `import advanced_alchemy.types` for custom column types.
- **Auth exclusions**: Public routes (`/health`, `/schema`) are listed as anchored regex patterns in `auth_exclude_paths` in `security.py` (e.g. `"^/$"` not `"/"`). All other routes require session auth.
- **Verification**: litestar-users requires `is_active=True` AND `is_verified=True` for session auth. `AUTO_VERIFY_USERS=true` in `.env` skips verification in dev. In production, `send_verification_token` in `services.py` must be implemented to deliver the JWT token.
- **Token delivery**: `send_verification_token` and `send_password_reset_token` in `UserService` are placeholder overrides that log tokens to console. Replace with email/SMS for production.
- **Tests**: Build a fresh `Litestar` app with in-memory SQLite (`create_all=True`) per test — no Alembic needed in tests.
