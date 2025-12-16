"""
Endpoints для управления кешем
"""
import time
import logging
from flask import Blueprint, request, jsonify
from backend.config.settings import SECURITY_HASH

logger = logging.getLogger(__name__)

cache_bp = Blueprint('cache', __name__)


@cache_bp.route('/api/cache/cleanup', methods=['POST'])
def manual_cache_cleanup():
    """Ручная ПОЛНАЯ очистка кеша (для тестирования)"""
    try:
        logger.info("🧹 Запущена ручная ПОЛНАЯ очистка кеша")
        
        from backend.core.cache_manager import bot_cache
        
        # Получаем статистику до очистки
        stats_before = bot_cache.get_stats()
        
        # Выполняем ПОЛНУЮ очистку (удаляем все файлы)
        bot_cache.clear_all()
        
        # Получаем статистику после очистки
        stats_after = bot_cache.get_stats()
        
        deleted_files = stats_before.get('total_files', 0)
        
        result = {
            "success": True,
            "message": "ПОЛНАЯ очистка кеша выполнена - удалены ВСЕ файлы",
            "stats": {
                "before": stats_before,
                "after": stats_after,
                "deleted_files": deleted_files
            },
            "timestamp": time.time()
        }
        
        logger.info(f"✅ Ручная ПОЛНАЯ очистка завершена! Удалено всех файлов: {deleted_files}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Ошибка ручной очистки кеша: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }), 500


@cache_bp.route(f'/{SECURITY_HASH}_delete_client_cache', methods=['POST'])
def delete_client_cache():
    """Удаляет кеш конкретного клиента"""
    try:
        logger.info(f"🗑️ ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_delete_client_cache")
        
        data = request.get_json()
        client_id = data.get('client_id')
        telegram_uid = data.get('telegram_uid')
        
        logger.info(f"🗑️ Запрос на удаление кеша: client_id={client_id}, telegram_uid={telegram_uid}")
        
        if not all([client_id, telegram_uid]):
            return jsonify({
                "success": False, 
                "error": "Требуются параметры client_id и telegram_uid"
            }), 400
        
        from backend.core.cache_manager import bot_cache
        
        cache_file_path = bot_cache._get_cache_file_path(client_id, telegram_uid)
        
        if cache_file_path.exists():
            try:
                cache_file_path.unlink()
                logger.info(f"✅ Удален файл кеша: {cache_file_path.name}")
                
                return jsonify({
                    "success": True,
                    "message": f"Кеш клиента успешно удален",
                    "deleted_file": cache_file_path.name,
                    "timestamp": time.time()
                })
                
            except OSError as e:
                logger.error(f"❌ Ошибка удаления файла кеша: {e}")
                return jsonify({
                    "success": False,
                    "error": f"Ошибка удаления файла: {str(e)}",
                    "timestamp": time.time()
                }), 500
        else:
            logger.info(f"📭 Файл кеша не найден: {cache_file_path.name}")
            return jsonify({
                "success": True,
                "message": "Файл кеша не найден (возможно, уже удален)",
                "timestamp": time.time()
            })
            
    except Exception as e:
        logger.error(f"❌ Ошибка в delete_client_cache: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }), 500

