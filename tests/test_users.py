from litestar.testing import TestClient

from tests.conftest import USER_EMAIL, USER_PASSWORD, make_token


def test_register(client: TestClient) -> None:
    resp = client.post(
        "/register", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == USER_EMAIL
    assert data["is_verified"] is True
    assert "password_hash" not in data


def test_register_duplicate(client: TestClient) -> None:
    client.post("/register", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    resp = client.post(
        "/register", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    assert resp.status_code == 409


def test_login_success(client: TestClient) -> None:
    client.post("/register", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    resp = client.post("/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert resp.status_code == 201


def test_login_wrong_password(client: TestClient) -> None:
    client.post("/register", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    resp = client.post("/login", json={"email": USER_EMAIL, "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client: TestClient) -> None:
    resp = client.post("/login", json={"email": "nobody@example.com", "password": "x"})
    assert resp.status_code == 401


def test_logout(authenticated_client: TestClient) -> None:
    resp = authenticated_client.post("/logout")
    assert resp.status_code == 201


def test_get_current_user(authenticated_client: TestClient) -> None:
    resp = authenticated_client.get("/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == USER_EMAIL
    assert "password_hash" not in data


def test_get_current_user_after_logout(authenticated_client: TestClient) -> None:
    authenticated_client.post("/logout")
    resp = authenticated_client.get("/users/me")
    assert resp.status_code == 401


def test_get_current_user_without_login(client: TestClient) -> None:
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_update_current_user(authenticated_client: TestClient) -> None:
    resp = authenticated_client.patch(
        "/users/me", json={"email": "updated@example.com"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "updated@example.com"
    assert "password_hash" not in resp.json()


def test_update_current_user_without_login(client: TestClient) -> None:
    resp = client.patch("/users/me", json={"email": "updated@example.com"})
    assert resp.status_code == 401


def test_health_no_auth_required(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


# --- Verification ---


def test_verify_with_valid_token(client: TestClient) -> None:
    resp = client.post(
        "/register", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    user_id = resp.json()["id"]
    token = make_token(user_id, aud="verify")
    resp = client.post(f"/verify?token={token}")
    assert resp.status_code == 201


def test_verify_with_invalid_token(client: TestClient) -> None:
    resp = client.post("/verify?token=garbage.token.value")
    assert resp.status_code in (400, 401)


# --- Forgot Password / Reset Password ---


def test_forgot_password_existing_user(authenticated_client: TestClient) -> None:
    resp = authenticated_client.post("/forgot-password", json={"email": USER_EMAIL})
    assert resp.status_code == 201


def test_forgot_password_nonexistent_user(client: TestClient) -> None:
    resp = client.post("/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 201


def test_reset_password_with_valid_token(client: TestClient) -> None:
    resp = client.post(
        "/register", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    user_id = resp.json()["id"]
    token = make_token(user_id, aud="reset_password")
    new_password = "NewSecret456!"
    resp = client.post(
        "/reset-password", json={"token": token, "password": new_password}
    )
    assert resp.status_code == 201
    resp = client.post("/login", json={"email": USER_EMAIL, "password": new_password})
    assert resp.status_code == 201


def test_reset_password_with_invalid_token(client: TestClient) -> None:
    resp = client.post("/reset-password", json={"token": "bad.token", "password": "x"})
    assert resp.status_code in (400, 401)


def test_reset_password_old_password_no_longer_works(client: TestClient) -> None:
    resp = client.post(
        "/register", json={"email": USER_EMAIL, "password": USER_PASSWORD}
    )
    user_id = resp.json()["id"]
    token = make_token(user_id, aud="reset_password")
    client.post("/reset-password", json={"token": token, "password": "NewSecret456!"})
    resp = client.post("/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert resp.status_code == 401
