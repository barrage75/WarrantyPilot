import argparse
import asyncio
import mailbox
from types import TracebackType


class LocalSmtpServer:
    def __init__(self, maildir_path: str, port: int = 0) -> None:
        self.maildir = mailbox.Maildir(maildir_path, create=True)
        self.port = port
        self.server: asyncio.Server | None = None

    async def start(self) -> "LocalSmtpServer":
        self.server = await asyncio.start_server(self._client, "127.0.0.1", self.port)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def __aenter__(self) -> "LocalSmtpServer":
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.stop()

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        sender = False
        recipient = False

        async def reply(value: bytes) -> None:
            writer.write(value + b"\r\n")
            await writer.drain()

        try:
            await reply(b"220 localhost SMTP")
            while line := await reader.readline():
                command = line.decode("ascii", errors="replace").strip().upper()
                if command.startswith(("EHLO ", "HELO ")):
                    await reply(b"250 localhost")
                elif command.startswith("MAIL FROM:"):
                    sender, recipient = True, False
                    await reply(b"250 OK")
                elif command.startswith("RCPT TO:") and sender:
                    recipient = True
                    await reply(b"250 OK")
                elif command == "DATA" and recipient:
                    await reply(b"354 End with dot")
                    content = bytearray()
                    while chunk := await reader.readline():
                        if chunk == b".\r\n":
                            self.maildir.add(bytes(content))
                            self.maildir.flush()
                            await reply(b"250 Delivered")
                            break
                        content.extend(chunk[1:] if chunk.startswith(b"..") else chunk)
                    sender, recipient = False, False
                elif command == "RSET":
                    sender, recipient = False, False
                    await reply(b"250 OK")
                elif command == "NOOP":
                    await reply(b"250 OK")
                elif command == "QUIT":
                    await reply(b"221 Bye")
                    break
                else:
                    await reply(b"503 Unsupported command or sequence")
        finally:
            writer.close()
            await writer.wait_closed()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2525)
    parser.add_argument("--maildir", default="runtime/mail")
    args = parser.parse_args()
    async with LocalSmtpServer(args.maildir, args.port):
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
