from sqlalchemy import update

from app.db.models.user import User


async def test_admin_requires_superuser(client, auth_headers):
    for path in ("/admin/users", "/admin/ai-logs", "/admin/activity-logs"):
        r = client.get(path, headers=auth_headers())
        assert r.status_code == 403, (path, r.text)


async def test_admin_endpoints(db, client, auth_headers):
    email = "admin@example.com"
    headers = auth_headers(email)
    await db.execute(update(User).where(User.email == email).values(is_superuser=1))
    await db.commit()

    r = client.get("/admin/users", headers=headers)
    assert r.status_code == 200
    assert any(u["email"] == email for u in r.json())

    r = client.get("/admin/ai-logs", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

    r = client.get("/admin/activity-logs", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


async def test_admin_requires_auth(client):
    assert client.get("/admin/users").status_code == 401
