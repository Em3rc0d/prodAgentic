from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import ssl
from typing import Any
from urllib.parse import unquote, urlparse

from domain.jobs.models import JobIntent, StreamLagMetrics, TransportMessage


class RedisProtocolError(RuntimeError):
    pass


class RedisCommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class RedisStreamsSettings:
    url: str
    stream: str = "prodagentic:jobs:v1"
    group: str = "prodagentic-workers-v1"
    dead_letter_stream: str = "prodagentic:jobs:dlq:v1"
    connect_timeout_seconds: float = 3.0

    @classmethod
    def from_env(cls) -> "RedisStreamsSettings":
        return cls(
            url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            stream=os.getenv("PRODAGENTIC_JOB_STREAM", "prodagentic:jobs:v1"),
            group=os.getenv("PRODAGENTIC_JOB_GROUP", "prodagentic-workers-v1"),
            dead_letter_stream=os.getenv(
                "PRODAGENTIC_JOB_DLQ_STREAM",
                "prodagentic:jobs:dlq:v1",
            ),
            connect_timeout_seconds=float(
                os.getenv("PRODAGENTIC_REDIS_CONNECT_TIMEOUT_SECONDS", "3")
            ),
        )


def _encode_command(parts: tuple[Any, ...]) -> bytes:
    encoded = []
    for part in parts:
        if isinstance(part, bytes):
            value = part
        else:
            value = str(part).encode("utf-8")
        encoded.append(
            b"$" + str(len(value)).encode("ascii") + b"\r\n" + value + b"\r\n"
        )
    return b"*" + str(len(encoded)).encode("ascii") + b"\r\n" + b"".join(encoded)


async def _read_resp(reader: asyncio.StreamReader):
    marker = await reader.readexactly(1)
    line = await reader.readline()
    if not line.endswith(b"\r\n"):
        raise RedisProtocolError("invalid RESP line terminator")
    payload = line[:-2]

    if marker == b"+":
        return payload.decode("utf-8")
    if marker == b"-":
        raise RedisCommandError(payload.decode("utf-8", errors="replace"))
    if marker == b":":
        return int(payload)
    if marker == b"$":
        size = int(payload)
        if size == -1:
            return None
        data = await reader.readexactly(size)
        terminator = await reader.readexactly(2)
        if terminator != b"\r\n":
            raise RedisProtocolError("invalid RESP bulk terminator")
        return data
    if marker == b"*":
        count = int(payload)
        if count == -1:
            return None
        return [await _read_resp(reader) for _ in range(count)]
    raise RedisProtocolError(f"unsupported RESP marker: {marker!r}")


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _field_map(values: list[Any]) -> dict[str, str]:
    if len(values) % 2:
        raise RedisProtocolError("stream field list must contain key/value pairs")
    return {
        _text(values[index]): _text(values[index + 1])
        for index in range(0, len(values), 2)
    }


class RedisStreamsTransport:
    """Minimal RESP2 Redis Streams adapter.

    Mongo remains authoritative. This adapter intentionally carries only job
    identity and integrity metadata, never the business payload itself.
    """

    def __init__(self, settings: RedisStreamsSettings):
        self.settings = settings
        parsed = urlparse(settings.url)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        self._host = parsed.hostname or "127.0.0.1"
        self._port = parsed.port or 6379
        self._username = unquote(parsed.username) if parsed.username else None
        self._password = unquote(parsed.password) if parsed.password else None
        path = parsed.path.strip("/")
        self._db = int(path) if path else 0
        self._ssl = ssl.create_default_context() if parsed.scheme == "rediss" else None

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                self._host,
                self._port,
                ssl=self._ssl,
                server_hostname=self._host if self._ssl else None,
            ),
            timeout=self.settings.connect_timeout_seconds,
        )
        try:
            if self._password is not None:
                if self._username:
                    await self._send_on(reader, writer, "AUTH", self._username, self._password)
                else:
                    await self._send_on(reader, writer, "AUTH", self._password)
            if self._db:
                await self._send_on(reader, writer, "SELECT", self._db)
            return reader, writer
        except Exception:
            writer.close()
            await writer.wait_closed()
            raise

    async def _send_on(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *parts: Any,
    ):
        writer.write(_encode_command(tuple(parts)))
        await writer.drain()
        return await _read_resp(reader)

    async def _command(self, *parts: Any):
        reader, writer = await self._open()
        try:
            return await self._send_on(reader, writer, *parts)
        finally:
            writer.close()
            await writer.wait_closed()

    async def ping(self) -> bool:
        return _text(await self._command("PING")) == "PONG"

    async def ensure_group(self) -> None:
        try:
            await self._command(
                "XGROUP",
                "CREATE",
                self.settings.stream,
                self.settings.group,
                "0",
                "MKSTREAM",
            )
        except RedisCommandError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, job: JobIntent) -> str:
        message_id = await self._command(
            "XADD",
            self.settings.stream,
            "*",
            "tenant_id",
            job.tenant_id,
            "job_id",
            job.job_id,
            "kind",
            job.kind,
            "payload_sha256",
            job.payload_sha256,
        )
        return _text(message_id)

    def _messages_from_response(self, response: Any) -> list[TransportMessage]:
        if not response:
            return []
        messages: list[TransportMessage] = []
        for stream_entry in response:
            if not isinstance(stream_entry, list) or len(stream_entry) != 2:
                raise RedisProtocolError("invalid XREADGROUP stream response")
            for raw_message in stream_entry[1] or []:
                message_id, raw_fields = raw_message
                fields = _field_map(raw_fields)
                messages.append(
                    TransportMessage(
                        message_id=_text(message_id),
                        tenant_id=fields["tenant_id"],
                        job_id=fields["job_id"],
                        kind=fields["kind"],
                        payload_sha256=fields["payload_sha256"],
                    )
                )
        return messages

    async def read(
        self,
        *,
        consumer: str,
        count: int = 1,
        block_ms: int = 1000,
    ) -> list[TransportMessage]:
        await self.ensure_group()
        response = await self._command(
            "XREADGROUP",
            "GROUP",
            self.settings.group,
            consumer,
            "COUNT",
            max(1, count),
            "BLOCK",
            max(0, block_ms),
            "STREAMS",
            self.settings.stream,
            ">",
        )
        return self._messages_from_response(response)

    async def recover_pending(
        self,
        *,
        consumer: str,
        min_idle_ms: int,
        count: int = 10,
    ) -> list[TransportMessage]:
        await self.ensure_group()
        response = await self._command(
            "XAUTOCLAIM",
            self.settings.stream,
            self.settings.group,
            consumer,
            max(0, min_idle_ms),
            "0-0",
            "COUNT",
            max(1, count),
        )
        if not response or len(response) < 2:
            return []
        synthetic = [[self.settings.stream.encode("utf-8"), response[1]]]
        return self._messages_from_response(synthetic)

    async def ack(self, message_id: str) -> None:
        await self._command(
            "XACK",
            self.settings.stream,
            self.settings.group,
            message_id,
        )

    async def dead_letter(self, message: TransportMessage, *, reason: str) -> str:
        message_id = await self._command(
            "XADD",
            self.settings.dead_letter_stream,
            "*",
            "source_message_id",
            message.message_id,
            "tenant_id",
            message.tenant_id,
            "job_id",
            message.job_id,
            "kind",
            message.kind,
            "payload_sha256",
            message.payload_sha256,
            "reason",
            reason[:1000],
        )
        return _text(message_id)

    async def lag_metrics(self) -> StreamLagMetrics:
        await self.ensure_group()
        stream_length = int(await self._command("XLEN", self.settings.stream))
        pending = await self._command(
            "XPENDING",
            self.settings.stream,
            self.settings.group,
        )
        pending_count = int(pending[0]) if pending else 0
        groups = await self._command("XINFO", "GROUPS", self.settings.stream)
        lag = None
        for raw_group in groups or []:
            group = _field_map(raw_group)
            if group.get("name") == self.settings.group:
                raw_lag = group.get("lag")
                lag = int(raw_lag) if raw_lag not in (None, "None") else None
                break
        return StreamLagMetrics(
            stream_length=stream_length,
            pending_count=pending_count,
            lag=lag,
        )

    async def close(self) -> None:
        return None
