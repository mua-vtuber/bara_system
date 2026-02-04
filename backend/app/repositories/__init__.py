from __future__ import annotations

from app.repositories.activity import ActivityRepository
from app.repositories.base import BaseRepository
from app.repositories.collected_info import CollectedInfoRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.good_example import GoodExampleRepository
from app.repositories.notification import NotificationRepository
from app.repositories.settings import SettingsRepository

__all__ = [
    "BaseRepository",
    "ActivityRepository",
    "CollectedInfoRepository",
    "ConversationRepository",
    "GoodExampleRepository",
    "NotificationRepository",
    "SettingsRepository",
]
