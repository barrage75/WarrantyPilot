from __future__ import annotations

import socket
import sys


class PortInUseError(RuntimeError):
    pass


def require_free_port(host: str = "127.0.0.1", port: int = 8100) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as error:
            raise PortInUseError(
                f"Port {port} on {host} is already in use; stop the existing Dell "
                "reproduction before running make p0."
            ) from error


def main() -> int:
    try:
        require_free_port()
    except PortInUseError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
