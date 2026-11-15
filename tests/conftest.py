"""Keep the test suite independent of cloud accounts and external services."""

import socket

import pytest


@pytest.fixture(autouse=True)
def disable_external_connections(monkeypatch, tmp_path):
    original_connect = socket.socket.connect

    def blocked(*args, **kwargs):
        raise AssertionError("Tests must use synthetic data and mocked external services")

    def connect_local_only(sock, address):
        # Windows asyncio uses a loopback TCP socketpair for internal wakeups.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        return blocked()

    monkeypatch.setattr(socket.socket, "connect", connect_local_only)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "absent-aws-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "absent-aws-credentials"))
