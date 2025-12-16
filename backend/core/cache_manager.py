#!/usr/bin/env python3
"""
JSON файловый кеш для ответов бота с 12-часовым временем жизни
Каждый клиент хранится в отдельном JSON файле
"""

import os
import time
import json
import logging
import glob
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

class BotResponseCache:
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.getenv('CACHE_DIR', '/app/cache')
        
        self.cache_dir = Path(cache_dir)
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"💾 Инициализирован файловый кеш: {self.cache_dir}")
        logger.info(f"🧹 Очистка кеша: каждый день в 00:00 (полное удаление всех файлов)")
    
    def _get_cache_file_path(self, client_id, telegram_uid):
        """Генерирует путь к файлу кеша для клиента"""
        # Безопасное имя файла (убираем потенциально опасные символы)
        safe_client_id = str(client_id).replace('/', '_').replace('\\', '_')
        safe_telegram_uid = str(telegram_uid).replace('/', '_').replace('\\', '_')
        filename = f"client_{safe_client_id}_{safe_telegram_uid}.json"
        return self.cache_dir / filename
    
    def _read_cache_file(self, cache_file_path):
        """Читает данные из файла кеша"""
        try:
            if not cache_file_path.exists():
                return None
            
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if not isinstance(cache_data, dict) or 'data' not in cache_data or 'timestamp' not in cache_data:
                logger.warning(f"⚠️ Некорректная структура файла кеша: {cache_file_path}")
                return None
            
            return cache_data
            
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.error(f"❌ Ошибка чтения файла кеша {cache_file_path}: {e}")
            try:
                cache_file_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
    
    def _write_cache_file(self, cache_file_path, data):
        """Записывает данные в файл кеша"""
        try:
            cache_data = {
                'data': data,
                'timestamp': time.time(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'expires_at': datetime.fromtimestamp(time.time() + 86400, timezone.utc).isoformat()  # Завтра в это же время
            }
            
            # Создаем временный файл для атомарной записи
            temp_file = cache_file_path.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Атомарно перемещаем файл
            temp_file.replace(cache_file_path)
            
            logger.info(f"💾 Сохранен кеш файл: {cache_file_path.name}")
            
        except (OSError, TypeError) as e:
            logger.error(f"❌ Ошибка записи файла кеша {cache_file_path}: {e}")
    
    def get(self, client_id, telegram_uid):
        """Получает данные из кеша"""
        
        cache_file_path = self._get_cache_file_path(client_id, telegram_uid)
        cache_data = self._read_cache_file(cache_file_path)
        
        if cache_data is None:
            logger.info(f"🔍 Файл кеша не найден: {cache_file_path.name}")
            return None
        
        current_time = time.time()
        cached_time = cache_data['timestamp']
        
        logger.info(f"⚡ Используем кешированные данные из файла: {cache_file_path.name}")
        logger.info(f"⏰ Возраст кеша: {(current_time - cached_time) // 60:.0f} минут")
        return cache_data['data']
    
    def set(self, client_id, telegram_uid, data):
        """Сохраняет данные в кеш"""
        cache_file_path = self._get_cache_file_path(client_id, telegram_uid)
        self._write_cache_file(cache_file_path, data)
        logger.info(f"💾 Сохранены данные в кеш для client_id={client_id}, telegram_uid={telegram_uid}")
    
    def clear_expired(self):
        """Очищает кеш (теперь просто вызывает полную очистку)"""
        logger.info("🧹 Вызван clear_expired() - выполняем полную очистку всех файлов")
        self.clear_all()
    
    def clear_all(self):
        """Полностью очищает весь кеш - удаляет ВСЕ файлы"""
        try:
            deleted_count = 0
            
            # Ищем ВСЕ JSON файлы в директории кеша
            for cache_file_path in self.cache_dir.glob("client_*.json"):
                try:
                    cache_file_path.unlink()
                    logger.debug(f"🗑️ Удален файл: {cache_file_path.name}")
                    deleted_count += 1
                except OSError as e:
                    logger.error(f"❌ Ошибка удаления файла {cache_file_path.name}: {e}")
            
            logger.info(f"🧹 ПОЛНАЯ очистка завершена! Удалено всех файлов: {deleted_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка полной очистки кеша: {e}")
    
    def get_by_client_id(self, client_id):
        """Получает данные из кеша по client_id (первый найденный)"""
        
        try:
            pattern = f"client_{client_id}_*.json"
            cache_files = list(self.cache_dir.glob(pattern))
            
            for cache_file_path in cache_files:
                cache_data = self._read_cache_file(cache_file_path)
                
                if cache_data is None:
                    continue
                
                current_time = time.time()
                cached_time = cache_data['timestamp']
                
                logger.info(f"🔍 Найдены кешированные данные для client_id {client_id}: {cache_file_path.name}")
                return cache_data['data']
            
            logger.info(f"🔍 Актуальные кешированные данные для client_id {client_id} не найдены")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска по client_id {client_id}: {e}")
            return None
    
    def get_stats(self):
        """Возвращает статистику кеша"""
        try:
            total_files = len(list(self.cache_dir.glob("client_*.json")))
            cache_size_mb = sum(f.stat().st_size for f in self.cache_dir.glob("client_*.json")) / (1024 * 1024)
            
            return {
                "total_files": total_files,
                "cached_items": total_files,
                "cache_cleanup": "daily at midnight",
                "cache_dir": str(self.cache_dir),
                "cache_size_mb": round(cache_size_mb, 2),
                "cache_type": "JSON файлы"
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики кеша: {e}")
            return {
                "total_files": 0,
                "error": str(e),
                "cache_dir": str(self.cache_dir)
            }

# Глобальный экземпляр кеша (очистка каждый день в полночь)
bot_cache = BotResponseCache()  # Очистка каждый день в полночь