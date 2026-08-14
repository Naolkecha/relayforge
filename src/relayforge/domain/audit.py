from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from relayforge.domain.common import new_id, utc_now


@dataclass(frozen=True, slots=True)
class AuditEvent:
    organization_id: UUID
    action: str
    resource_type: str
    resource_id: str
    actor_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
