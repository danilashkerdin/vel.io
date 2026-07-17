import re
from pydantic import BaseModel, field_validator
from typing import Optional, Any


class TerritoryUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    image_url: str | None = None
    description: str | None = None
    link_url: str | None = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError("Цвет должен быть в формате #RRGGBB")
        return v
