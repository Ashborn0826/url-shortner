from datetime import datetime

from pydantic import BaseModel, field_validator

from app.shortcode import validate_custom_code

URL_PATTERN = r"^https?://[^\s]+$"


class CreateUrlRequest(BaseModel):
    long_url: str
    custom_code: str | None = None

    @field_validator("long_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        import re

        if not re.match(URL_PATTERN, v):
            raise ValueError("must be a valid http(s) URL")
        return v

    @field_validator("custom_code")
    @classmethod
    def _validate_custom(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_custom_code(v):
            raise ValueError("must be 3-32 chars, [A-Za-z0-9_-] only")
        return v


class CreateUrlResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime