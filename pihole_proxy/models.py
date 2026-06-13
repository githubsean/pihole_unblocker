"""
Data models for Pi-hole Proxy responses.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StatusResponse:
    """Response data for the blocking status API endpoint."""

    status: str  # "enabled", "disabled", or "unknown"
    timer: int = 0
    is_blocked: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON response."""
        result = {
            "status": self.status,
            "timer": self.timer,
            "is_blocked": self.is_blocked,
        }
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class ApiResponse:
    """Generic API response wrapper."""

    status: str  # "success" or "error"
    message: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON response."""
        result = {"status": self.status}
        if self.message:
            result["message"] = self.message
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class DisableRequest:
    """Parsed data from a disable request body."""

    timer: int = 5

    @classmethod
    def from_dict(cls, data: dict) -> "DisableRequest":
        """Parse and validate from a dictionary."""
        minutes = data.get("timer", 5)
        if not isinstance(minutes, int) or minutes < 0 or minutes > 60:
            raise ValueError(
                "Invalid input. Timer must be a number between 0 and 60 minutes."
            )
        return cls(timer=minutes)