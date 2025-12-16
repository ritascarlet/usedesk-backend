"""
Routes package - Все endpoints приложения
"""
from backend.routes.health import health_bp
from backend.routes.cache import cache_bp
from backend.routes.telegram import telegram_bp
from backend.routes.usedesk import usedesk_bp
from backend.routes.debug import debug_bp

__all__ = ['health_bp', 'cache_bp', 'telegram_bp', 'usedesk_bp', 'debug_bp']
