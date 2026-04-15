# handlers package
from handlers.user import register as register_user
from handlers.admin import register as register_admin


def register_all(bot) -> None:
    """يُسجّل كل handlers مع الـ bot."""
    register_user(bot)
    register_admin(bot)
