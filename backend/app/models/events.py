from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class Event:
    """Base event. All events carry a UTC timestamp."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -- Feed / Content events --------------------------------------------------

@dataclass(frozen=True)
class NewPostDiscoveredEvent(Event):
    platform: str = ""
    post_id: str = ""
    title: str = ""
    author: str = ""
    url: str = ""


@dataclass(frozen=True)
class CommentPostedEvent(Event):
    platform: str = ""
    activity_id: int = 0
    post_id: str = ""
    comment_id: str = ""


@dataclass(frozen=True)
class PostCreatedEvent(Event):
    platform: str = ""
    activity_id: int = 0
    post_id: str = ""
    url: str = ""


@dataclass(frozen=True)
class UpvoteEvent(Event):
    platform: str = ""
    post_id: str = ""


# -- Notification events ----------------------------------------------------

@dataclass(frozen=True)
class NotificationReceivedEvent(Event):
    platform: str = ""
    notification_id: str = ""
    notification_type: str = ""
    actor_name: str = ""
    post_id: str = ""


# -- Config events ----------------------------------------------------------

@dataclass(frozen=True)
class ConfigChangedEvent(Event):
    section: str = ""
    old_value: Any = None
    new_value: Any = None


# -- Platform events --------------------------------------------------------

@dataclass(frozen=True)
class PlatformErrorEvent(Event):
    platform: str = ""
    error_type: str = ""
    message: str = ""
    status_code: Optional[int] = None


# -- System events ----------------------------------------------------------

@dataclass(frozen=True)
class EmergencyStopEvent(Event):
    source: str = ""


@dataclass(frozen=True)
class HealthCheckEvent(Event):
    status: str = ""
    checks: list[dict[str, Any]] = field(default_factory=list)


# -- LLM events -------------------------------------------------------------

@dataclass(frozen=True)
class LLMRequestStartEvent(Event):
    request_id: str = ""
    model: str = ""
    prompt_length: int = 0


@dataclass(frozen=True)
class LLMResponseCompleteEvent(Event):
    request_id: str = ""
    model: str = ""
    response_length: int = 0
    duration_ms: float = 0.0


# -- Approval events --------------------------------------------------------

@dataclass(frozen=True)
class ApprovalRequestedEvent(Event):
    activity_id: int = 0
    activity_type: str = ""
    platform: str = ""
    content_preview: str = ""


@dataclass(frozen=True)
class ApprovalResolvedEvent(Event):
    activity_id: int = 0
    approved: bool = False


# -- Voice events -----------------------------------------------------------

@dataclass(frozen=True)
class VoiceCommandEvent(Event):
    transcript: str = ""
    confidence: float = 0.0


# -- Bot status events ------------------------------------------------------

@dataclass(frozen=True)
class BotStatusChangedEvent(Event):
    old_status: str = ""
    new_status: str = ""
    reason: str = ""


# -- Task queue events ------------------------------------------------------

@dataclass(frozen=True)
class TaskQueuedEvent(Event):
    platform: str = ""
    action_type: str = ""
    priority: int = 0


@dataclass(frozen=True)
class TaskCompletedEvent(Event):
    platform: str = ""
    action_type: str = ""
    success: bool = True
    error: Optional[str] = None


# -- Mission events ---------------------------------------------------------

@dataclass(frozen=True)
class MissionCreatedEvent(Event):
    mission_id: int = 0
    topic: str = ""
    urgency: str = "normal"


@dataclass(frozen=True)
class MissionPostPublishedEvent(Event):
    mission_id: int = 0
    platform: str = ""
    post_id: str = ""


@dataclass(frozen=True)
class MissionResponseReceivedEvent(Event):
    mission_id: int = 0
    platform: str = ""
    responder: str = ""
    content_preview: str = ""


@dataclass(frozen=True)
class MissionCompletedEvent(Event):
    mission_id: int = 0
    topic: str = ""
    response_count: int = 0


# -- Bot response events ---------------------------------------------------

@dataclass(frozen=True)
class BotResponseGeneratedEvent(Event):
    """Fired after the bot generates any response (comment, reply, post)."""
    platform: str = ""
    action_type: str = ""  # "comment", "reply", "post"
    original_content: str = ""  # the post/notification content that triggered this
    bot_response: str = ""  # what the bot generated
    post_id: str = ""
    author: str = ""  # author of the original content