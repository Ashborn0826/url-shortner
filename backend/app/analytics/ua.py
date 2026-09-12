"""User-Agent parser.

Wraps the `user-agents` PyPI package to produce a small structured
record: browser family, OS family, device family.
"""
from dataclasses import dataclass

from user_agents import parse as ua_parse


@dataclass(frozen=True)
class UserAgentInfo:
    browser: str
    os: str
    device: str


def parse_user_agent(user_agent: str | None) -> UserAgentInfo:
    """Parse a User-Agent string into structured fields.

    Returns "Unknown" / "Desktop" placeholders for missing or empty UA strings.
    """
    if not user_agent:
        return UserAgentInfo(browser="Unknown", os="Unknown", device="Unknown")

    parsed = ua_parse(user_agent)
    if parsed.is_mobile or parsed.is_tablet:
        device = parsed.device.family or "Mobile"
    else:
        device = "Desktop"

    return UserAgentInfo(
        browser=parsed.browser.family or "Unknown",
        os=parsed.os.family or "Unknown",
        device=device,
    )