import io


def _fake_pdf() -> bytes:
    return b"%PDF-1.4 fake pdf for upload test"


def test_upload_list_delete(client, auth_headers):
    r = client.post(
        "/resumes/upload",
        headers=auth_headers(),
        files={"file": ("resume.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        data={"title": "My Resume"},
    )
    assert r.status_code == 201, r.text
    resume_id = r.json()["id"]

    r = client.get("/resumes", headers=auth_headers())
    assert r.status_code == 200
    assert any(x["id"] == resume_id for x in r.json())

    r = client.get(f"/resumes/{resume_id}", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["title"] == "My Resume"

    assert client.delete(f"/resumes/{resume_id}", headers=auth_headers()).status_code == 204
    assert client.get(f"/resumes/{resume_id}", headers=auth_headers()).status_code == 404


def test_upload_requires_file(client, auth_headers):
    r = client.post("/resumes/upload", headers=auth_headers(), data={"title": "No file"})
    assert r.status_code == 422


def test_resume_isolation(client, auth_headers):
    r = client.post(
        "/resumes/upload",
        headers=auth_headers(),
        files={"file": ("resume.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        data={"title": "Private"},
    )
    resume_id = r.json()["id"]

    other = auth_headers("other@example.com")
    assert client.get(f"/resumes/{resume_id}", headers=other).status_code == 404
    assert client.delete(f"/resumes/{resume_id}", headers=other).status_code == 404

    r = client.get("/resumes", headers=other)
    assert all(x["id"] != resume_id for x in r.json())
