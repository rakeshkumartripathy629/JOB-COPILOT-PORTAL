from tests.helpers import create_notification


async def _user_id(client, headers) -> int:
    r = client.get("/users/me", headers=headers)
    return r.json()["id"]


async def test_notification_flow(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    n1 = await create_notification(db, user_id, title="Unread", is_read=0)
    await create_notification(db, user_id, title="Read", is_read=1)

    r = client.get("/notifications", headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get("/notifications/unread-count", headers=auth_headers())
    assert r.json() == {"unread": 1}

    assert client.patch(f"/notifications/{n1}/read", headers=auth_headers()).status_code == 200
    r = client.get("/notifications/unread-count", headers=auth_headers())
    assert r.json() == {"unread": 0}

    await create_notification(db, user_id, title="Another", is_read=0)
    r = client.get("/notifications/unread-count", headers=auth_headers())
    assert r.json() == {"unread": 1}
    assert client.post("/notifications/read-all", headers=auth_headers()).status_code == 200
    r = client.get("/notifications/unread-count", headers=auth_headers())
    assert r.json() == {"unread": 0}

    assert client.delete(f"/notifications/{n1}", headers=auth_headers()).status_code == 204
    remaining = client.get("/notifications", headers=auth_headers()).json()
    assert len(remaining) == 2
    assert all(x["id"] != n1 for x in remaining)


async def test_notification_isolation(db, client, auth_headers):
    user_id = await _user_id(client, auth_headers())
    n1 = await create_notification(db, user_id)

    other = auth_headers("other@example.com")
    assert client.patch(f"/notifications/{n1}/read", headers=other).status_code == 404
    assert client.delete(f"/notifications/{n1}", headers=other).status_code == 404
    r = client.get("/notifications/unread-count", headers=other)
    assert r.json() == {"unread": 0}
