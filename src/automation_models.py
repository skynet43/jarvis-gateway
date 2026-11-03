"""Validated automation request models and immutable payload digests."""
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Category = Literal["windows", "browser"]
Action = Literal[
    "list_files",
    "file_metadata",
    "read_text",
    "list_processes",
    "start_process",
    "stop_process",
    "browser_create",
    "browser_close",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_fill",
    "browser_screenshot",
]
Risk = Literal["low", "medium", "high"]

ACTION_CATEGORY = {
    "list_files": "windows", "file_metadata": "windows", "read_text": "windows",
    "list_processes": "windows", "start_process": "windows", "stop_process": "windows",
    "browser_create": "browser", "browser_close": "browser",
    "browser_navigate": "browser", "browser_snapshot": "browser",
    "browser_click": "browser", "browser_fill": "browser",
    "browser_screenshot": "browser",
}
ACTION_RISK = {
    "start_process": "high", "stop_process": "high",
    "browser_click": "high", "browser_fill": "high",
    "browser_navigate": "medium", "browser_screenshot": "medium",
}


class AutomationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category
    action: Action
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk: Risk = "low"

    @model_validator(mode="after")
    def validate_exact_action(self):
        if ACTION_CATEGORY[self.action] != self.category:
            raise ValueError("Action does not belong to category")
        encoded = json.dumps(self.arguments, separators=(",", ":"), sort_keys=True)
        if len(encoded.encode("utf-8")) > 8192:
            raise ValueError("Arguments exceed 8192 bytes")
        self.risk = ACTION_RISK.get(self.action, "low")
        return self


def canonical_payload(request: AutomationRequest) -> str:
    return json.dumps(request.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)


def payload_digest(request: AutomationRequest) -> str:
    return hashlib.sha256(canonical_payload(request).encode("utf-8")).hexdigest()
