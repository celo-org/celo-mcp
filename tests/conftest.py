import socket
import threading
import time

import pytest
import uvicorn

from celo_mcp.http_app import build_app


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ThreadedServer:
    def __init__(self, app, port: int):
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self):
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return
            time.sleep(0.05)
        raise RuntimeError("uvicorn did not start in time")

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)


@pytest.fixture
def http_server():
    """Starts the real ASGI app on a free port; yields the base http://host:port."""
    port = _free_port()
    app = build_app()
    srv = _ThreadedServer(app, port)
    srv.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.stop()
