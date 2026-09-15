"""Regression guard for EKA-32: the documented global 60/min/IP rate limit
must actually be enforced, i.e. SlowAPIMiddleware must be registered and the
limiter must carry the documented default limits."""
from slowapi.middleware import SlowAPIMiddleware

import main


def test_slowapi_middleware_registered():
    middleware_classes = [m.cls for m in main.app.user_middleware]
    assert SlowAPIMiddleware in middleware_classes, (
        "SlowAPIMiddleware missing — default_limits are dead config without it"
    )


def test_global_default_limits_documented_value():
    rendered = [str(item.limit) for group in main.limiter._default_limits for item in group]
    assert "60 per 1 minute" in rendered, (
        f"global default limit drifted from the documented 60/minute: {rendered}"
    )


def test_limiter_wired_into_app_state():
    assert main.app.state.limiter is main.limiter
