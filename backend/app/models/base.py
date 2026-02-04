from __future__ import annotations

from pydantic import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    """Project-wide base model with ``from_attributes`` enabled."""

    model_config = {"from_attributes": True}
