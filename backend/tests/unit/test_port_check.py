import socket

import pytest

from app.core.port_check import PortInUseError, require_free_port


def test_require_free_port_rejects_a_bound_loopback_socket() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = int(listener.getsockname()[1])

        with pytest.raises(PortInUseError, match="already in use"):
            require_free_port(port=port)
