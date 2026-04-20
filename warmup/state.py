from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import time


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(slots=True)
class SharedState:
    peer_id: str
    last_seen_ms: int
    role: str
    status: str

    @classmethod
    def fresh(
        cls,
        peer_id: str,
        role: str = "carrier",
        status: str = "ready",
    ) -> "SharedState":
        return cls(
            peer_id=peer_id,
            last_seen_ms=now_ms(),
            role=role,
            status=status,
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SharedState":
        return cls(
            peer_id=str(payload["peer_id"]),
            last_seen_ms=int(payload["last_seen_ms"]),
            role=str(payload["role"]),
            status=str(payload["status"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "last_seen_ms": self.last_seen_ms,
            "role": self.role,
            "status": self.status,
        }

    def touch(self, *, status: str | None = None) -> None:
        self.last_seen_ms = now_ms()
        if status is not None:
            self.status = status

    def age_ms(self) -> int:
        return now_ms() - self.last_seen_ms
