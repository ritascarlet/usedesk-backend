"""
UseDesk Backend - Главный файл приложения
Версия 2.1 (Refactored)
"""
import logging
import threading
import time
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

from backend.config.settings import APP_VERSION, DEBUG_MODE, print_config

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheCleanupScheduler:
    """Планировщик автоматической очистки кеша каждый день в полночь"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_cleanup_date = None
        
    def start(self):
        """Запускает фоновый поток очистки кеша"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self.thread.start()
            logger.info("🧹 Запущен планировщик очистки кеша (каждый день в 00:00)")
    
    def stop(self):
        """Останавливает фоновый поток"""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _cleanup_loop(self):
        """Основной цикл проверки времени и очистки"""
        while self.running:
            try:
                now = datetime.now()
                current_date = now.date()
                
                if (now.hour == 0 and now.minute == 0 and 
                    self.last_cleanup_date != current_date):
                    
                    logger.info("🕛 Полночь! Запускаем автоочистку кеша...")
                    self._perform_cleanup()
                    self.last_cleanup_date = current_date
                    
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в планировщике очистки кеша: {e}")
                time.sleep(60)
    
    def _perform_cleanup(self):
        """Выполняет ПОЛНУЮ очистку кеша - удаляет ВСЕ файлы"""
        try:
            from backend.core.cache_manager import bot_cache
            
            # Получаем статистику до очистки
            stats_before = bot_cache.get_stats()
            
            # Выполняем ПОЛНУЮ очистку (удаляем все файлы)
            bot_cache.clear_all()
            
            # Получаем статистику после очистки
            stats_after = bot_cache.get_stats()
            
            # Логируем результат
            deleted_files = stats_before.get('total_files', 0)
            logger.info(f"🧹 ПОЛНАЯ очистка кеша завершена! Удалено всех файлов: {deleted_files}")
            logger.info(f"📊 Кеш полностью очищен! Файлов: {stats_after.get('total_files', 0)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при полной очистке кеша: {e}")


# Создаем глобальный экземпляр планировщика
cache_scheduler = CacheCleanupScheduler()


# Регистрируем все blueprints
from backend.routes import health_bp, cache_bp, telegram_bp, usedesk_bp
from backend.routes.outline import outline_bp
from backend.routes.debug import debug_bp

app.register_blueprint(health_bp)
app.register_blueprint(cache_bp)
app.register_blueprint(telegram_bp)
app.register_blueprint(usedesk_bp)
app.register_blueprint(outline_bp)
app.register_blueprint(debug_bp)

logger.info("✅ Все blueprints зарегистрированы")


# Error handlers
@app.errorhandler(404)
def not_found(error):
    logger.error(f"❌ 404 - Страница не найдена: {error}")
    return jsonify({"error": "Endpoint не найден"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    logger.error(f"❌ 405 - Метод не разрешен: {error}")
    return jsonify({"error": "Метод не разрешен"}), 405


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ 500 - Внутренняя ошибка сервера: {error}")
    return jsonify({"error": "Внутренняя ошибка сервера"}), 500


# Инициализация при запуске модуля
def init_app():
    """Инициализация приложения"""
    try:
        print_config()
        
        cache_scheduler.start()
        logger.info("🚀 Планировщик кеша запущен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")


init_app()


if __name__ == '__main__':
    print("🚀 Запуск UseDesk Backend...")
    print(f"🔧 Версия {APP_VERSION}")
    print("🐍 Режим: Прямой запуск Flask (для разработки)")
    print("⚠️  Для production используйте gunicorn через run_app.py")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=DEBUG_MODE
    )

