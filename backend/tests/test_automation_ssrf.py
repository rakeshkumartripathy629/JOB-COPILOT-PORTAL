import socket

import pytest
from fastapi import HTTPException

from app.services.automation_service import _is_private_host, _validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8001/jobs/1",
        "http://127.0.0.1/secret",
        "http://10.0.0.5/apply",
        "http://172.16.5.5/apply",
        "http://192.168.1.10/job",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/apply",
        "ftp://example.com/job",
        "file:///etc/passwd",
        "http://metadata.google.internal/",
    ],
)
def test_validate_public_url_rejects_internal(url):
    with pytest.raises(HTTPException) as exc:
        _validate_public_url(url)
    assert exc.value.status_code == 400


def test_validate_public_url_allows_public_host(monkeypatch):
    def fake_getaddrinfo(host, port, proto=socket.IPPROTO_TCP):
        assert host == "jobs.example.com"
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    _validate_public_url("https://jobs.example.com/apply")


def test_is_private_host_blocks_unresolvable(monkeypatch):
    def fail_getaddrinfo(host, port, proto=socket.IPPROTO_TCP):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fail_getaddrinfo)
    assert _is_private_host("not-a-real-host.invalid") is True
