def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_signup_and_login(client):
    r = client.post(
        "/auth/signup",
        json={"email": "new@example.com", "password": "Password123!", "full_name": "New User"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "new@example.com"

    r = client.post("/auth/login", json={"email": "new@example.com", "password": "Password123!"})
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()


def test_duplicate_signup(client):
    payload = {"email": "dup@example.com", "password": "Password123!", "full_name": "Dup"}
    assert client.post("/auth/signup", json=payload).status_code == 201
    r = client.post("/auth/signup", json=payload)
    assert r.status_code == 400


def test_login_wrong_password(client):
    client.post("/auth/signup", json={"email": "w@example.com", "password": "Password123!", "full_name": "W"})
    r = client.post("/auth/login", json={"email": "w@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/users/me").status_code == 401


def test_me(client, auth_headers):
    r = client.get("/users/me", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


def test_refresh_flow(client):
    client.post("/auth/signup", json={"email": "r@example.com", "password": "Password123!", "full_name": "R"})
    r = client.post("/auth/login", json={"email": "r@example.com", "password": "Password123!"})
    assert r.status_code == 200
    r = client.post("/auth/refresh")
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_without_cookie(client):
    assert client.post("/auth/refresh").status_code == 401


def test_logout_revokes_refresh(client):
    client.post("/auth/signup", json={"email": "l@example.com", "password": "Password123!", "full_name": "L"})
    client.post("/auth/login", json={"email": "l@example.com", "password": "Password123!"})
    assert client.post("/auth/logout").status_code == 200
    assert client.post("/auth/refresh").status_code == 401
