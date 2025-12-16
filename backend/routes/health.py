"""
Health check и тестовые endpoints
"""
import logging
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health_check():
    """Эндпоинт для проверки здоровья приложения"""
    from backend.core.cache_manager import bot_cache
    cache_stats = bot_cache.get_stats()
    
    return jsonify({
        "status": "ok", 
        "message": "UseDesk Backend работает",
        "cache": cache_stats,
        "performance": "optimized"
    })


@health_bp.route('/test')
def test_endpoint():
    """Тестовый эндпоинт для проверки работы Flask"""
    logger.info("🧪 Тестовый эндпоинт вызван")
    return jsonify({"status": "ok", "message": "Flask работает!"})

