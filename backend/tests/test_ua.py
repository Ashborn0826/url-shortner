from app.analytics.ua import parse_user_agent


def test_chrome_on_windows_desktop():
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    info = parse_user_agent(ua)
    assert info.browser == "Chrome"
    assert info.os == "Windows"
    assert info.device == "Desktop"


def test_safari_ios_on_iphone():
    ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    )
    info = parse_user_agent(ua)
    assert info.browser == "Mobile Safari"
    assert info.os == "iOS"
    # iPhone is mobile, so device family is reported (iPhone) rather than generic Mobile
    assert info.device != "Desktop"


def test_firefox_on_linux_desktop():
    ua = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
    info = parse_user_agent(ua)
    assert info.browser == "Firefox"
    assert info.os == "Linux"
    assert info.device == "Desktop"


def test_empty_user_agent_returns_unknown():
    info = parse_user_agent("")
    assert info.browser == "Unknown"
    assert info.os == "Unknown"
    assert info.device == "Unknown"


def test_none_user_agent_returns_unknown():
    info = parse_user_agent(None)
    assert info.browser == "Unknown"
    assert info.os == "Unknown"
    assert info.device == "Unknown"