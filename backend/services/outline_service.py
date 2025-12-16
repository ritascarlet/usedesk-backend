"""
Сервис для работы с Outline API
"""
import logging
import requests
import time
import markdown
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.config.outline import (
    get_outline_config,
    is_outline_enabled,
    DEFAULT_CHECKLIST
)

logger = logging.getLogger(__name__)


def _markdown_to_html(markdown_text: str) -> str:
    """
    Конвертирует Markdown в HTML используя библиотеку markdown.
    Поддерживает:
    - Таблицы
    - Code blocks с подсветкой
    - Списки (в том числе чекбоксы)
    - Blockquotes
    - Автоссылки
    - Outline callouts (:::warning, :::info, :::tip)
    
    Args:
        markdown_text: Исходный Markdown текст
        
    Returns:
        HTML строка
    """
    if not markdown_text:
        return ""
    
    import re
    markdown_text = re.sub(r'!\[([^\]]*)\]\(([^"\)]+)(?:\s+"([^"]*)")?\)', '', markdown_text)
    
    markdown_text = re.sub(
        r':::warning\s*\n([\s\S]*?)\n:::',
        r'<div class="callout callout-danger"><div class="callout-icon">⚠️</div><div class="callout-content">\1</div></div>',
        markdown_text,
        flags=re.MULTILINE
    )
    
    markdown_text = re.sub(
        r':::(info|note)\s*\n([\s\S]*?)\n:::',
        r'<div class="callout callout-info"><div class="callout-icon">ℹ️</div><div class="callout-content">\2</div></div>',
        markdown_text,
        flags=re.MULTILINE
    )
    
    markdown_text = re.sub(
        r':::tip\s*\n([\s\S]*?)\n:::',
        r'<div class="callout callout-tip"><div class="callout-icon">💡</div><div class="callout-content">\1</div></div>',
        markdown_text,
        flags=re.MULTILINE
    )
    
    markdown_text = re.sub(
        r':::(success|check)\s*\n([\s\S]*?)\n:::',
        r'<div class="callout callout-success"><div class="callout-icon">✅</div><div class="callout-content">\2</div></div>',
        markdown_text,
        flags=re.MULTILINE
    )
    
    markdown_text = re.sub(
        r':::(danger|error)\s*\n([\s\S]*?)\n:::',
        r'<div class="callout callout-danger"><div class="callout-icon">❌</div><div class="callout-content">\2</div></div>',
        markdown_text,
        flags=re.MULTILINE
    )
    
    md = markdown.Markdown(extensions=[
        'extra',
        'nl2br',
        'sane_lists',
        'codehilite',
        'toc',
        'admonition',
    ])
    
    html = md.convert(markdown_text)
    
    return html


def _normalize_icon(icon: Optional[str]) -> str:
    """
    Нормализует иконку документа.
    Если иконка - это текст (например "notepad"), возвращает дефолтный эмодзи 📄.
    Если иконка - эмодзи или отсутствует, возвращает её или дефолтный эмодзи.
    
    Args:
        icon: Иконка документа из Outline
        
    Returns:
        Нормализованная иконка (эмодзи)
    """
    if not icon:
        return '📄'
    
    if icon.isalnum() and icon.isascii():
        logger.debug(f"   🔄 Заменяем текстовую иконку '{icon}' на эмодзи 📄")
        return '📄'
    
    return icon


class OutlineService:
    """Сервис для взаимодействия с Outline API"""
    
    def __init__(self):
        self.config = get_outline_config()
        self.base_url = self.config['base_url'].rstrip('/')
        self.api_token = self.config['api_token']
        self.timeout = self.config['request_timeout']
        self.max_retries = self.config['max_retries']
        
        # Кеш для документов
        self._cache = {}
        self._cache_timestamps = {}
        
        if is_outline_enabled():
            logger.info("✅ Outline сервис инициализирован")
            logger.info(f"📍 Base URL: {self.base_url}")
        else:
            logger.warning("⚠️ Outline интеграция отключена - используется fallback чеклист")
    
    def _get_headers(self) -> Dict[str, str]:
        """Возвращает заголовки для запросов к Outline API"""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _is_cache_valid(self, document_id: str) -> bool:
        """Проверяет валидность кеша для документа"""
        if document_id not in self._cache:
            return False
        
        cache_age = time.time() - self._cache_timestamps.get(document_id, 0)
        cache_ttl = self.config['cache_ttl']
        
        is_valid = cache_age < cache_ttl
        
        if is_valid:
            logger.info(f"⚡ Используем кешированный документ (возраст: {int(cache_age)}с)")
        
        return is_valid
    
    def _set_cache(self, document_id: str, data: Dict[str, Any]):
        """Сохраняет документ в кеш"""
        self._cache[document_id] = data
        self._cache_timestamps[document_id] = time.time()
        logger.info(f"💾 Документ сохранен в кеш: {document_id}")
    
    def _clear_cache(self, document_id: Optional[str] = None):
        """Очищает кеш для документа или весь кеш"""
        if document_id:
            self._cache.pop(document_id, None)
            self._cache_timestamps.pop(document_id, None)
            logger.info(f"🗑️ Кеш очищен для документа: {document_id}")
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("🗑️ Весь кеш Outline очищен")
    
    def get_document(self, document_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Получает документ из Outline
        
        Args:
            document_id: ID документа в Outline
            use_cache: Использовать ли кеш
            
        Returns:
            Данные документа или None при ошибке
        """
        # Проверяем кеш
        if use_cache and self._is_cache_valid(document_id):
            return self._cache[document_id]
        
        # Проверяем, включена ли интеграция
        if not is_outline_enabled():
            logger.warning("⚠️ Outline отключен, используем fallback")
            logger.warning(f"   Base URL: {self.base_url}")
            logger.warning(f"   API Token длина: {len(self.api_token)} символов")
            logger.warning(f"   Document ID: {document_id}")
            return None
        
        logger.info(f"📡 Запрос документа из Outline: {document_id}")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info(f"   API Token установлен: {'✓' if self.api_token else '✗'}")
        
        # Делаем запрос к API (используем export для получения полного контента)
        url = f"{self.base_url}/api/documents.export"
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json={'id': document_id},
                    headers=self._get_headers(),
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok') or 'data' in data:
                        # documents.export возвращает данные как строку в поле 'data'
                        if isinstance(data.get('data'), str):
                            markdown_content = data['data']
                            logger.info(f"✅ Документ экспортирован из Outline")
                            logger.info(f"   Размер контента: {len(markdown_content)} символов")
                            
                            # Формируем объект для кеша
                            document_data = {
                                'title': 'Чеклист для поддержки',
                                'text': markdown_content,
                                'id': document_id
                            }
                            
                            # Сохраняем в кеш
                            self._set_cache(document_id, document_data)
                            
                            return document_data
                        else:
                            logger.error(f"❌ Неожиданный формат ответа от Outline: {type(data.get('data'))}")
                            return None
                    else:
                        logger.error(f"❌ Некорректный ответ от Outline: {data}")
                        return None
                
                elif response.status_code == 401:
                    logger.error("❌ Ошибка авторизации Outline - проверьте API token")
                    return None
                
                elif response.status_code == 404:
                    logger.error(f"❌ Документ не найден: {document_id}")
                    return None
                
                else:
                    logger.error(f"❌ Ошибка Outline API: {response.status_code} - {response.text}")
                    
                    if attempt < self.max_retries:
                        logger.info(f"🔄 Повторная попытка {attempt + 1}/{self.max_retries}...")
                        time.sleep(1 * attempt)  # Экспоненциальная задержка
                        continue
                    
                    return None
            
            except requests.exceptions.Timeout:
                logger.error(f"⏰ Таймаут при запросе к Outline (попытка {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)
                    continue
                return None
            
            except requests.exceptions.ConnectionError:
                logger.error(f"🔌 Ошибка подключения к Outline (попытка {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)
                    continue
                return None
            
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка при запросе к Outline: {e}")
                return None
        
        return None
    
    def get_collection_documents(self, collection_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Получает список документов из коллекции
        
        Args:
            collection_id: ID коллекции в Outline
            
        Returns:
            Список документов или None при ошибке
        """
        if not is_outline_enabled():
            logger.warning("⚠️ Outline отключен")
            return None
        
        logger.info(f"📚 Запрос списка документов коллекции: {collection_id}")
        
        url = f"{self.base_url}/api/collections.documents"
        
        try:
            response = requests.post(
                url,
                json={'id': collection_id},
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok') and 'data' in data:
                    documents = data['data']
                    logger.info(f"✅ Найдено документов в коллекции: {len(documents)}")
                    
                    # Фильтруем, чтобы получить только документы верхнего уровня
                    # (без вложенных children для простоты)
                    return documents
                else:
                    logger.error(f"❌ Некорректный ответ от Outline: {data}")
                    return None
            else:
                logger.error(f"❌ Ошибка Outline API: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка документов: {e}")
            return None
    
    def get_checklist_collection(self, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Получает всю коллекцию чеклистов с контентом каждого документа
        
        Args:
            use_cache: Использовать ли кеш
            force_refresh: Принудительно обновить из Outline
            
        Returns:
            Словарь с коллекцией документов:
            {
                'title': str,
                'documents': [
                    {
                        'id': str,
                        'title': str,
                        'content': str (markdown),
                        'url': str,
                        'icon': str,
                        'color': str
                    },
                    ...
                ],
                'from_outline': bool,
                'from_cache': bool
            }
        """
        try:
            collection_id = self.config.get('collection_id')
            
            if not collection_id:
                logger.warning("⚠️ Collection ID не установлен, используем fallback")
                return self._get_fallback_collection()
            
            # Принудительное обновление - очищаем кеш
            if force_refresh:
                logger.info("🔄 Принудительное обновление коллекции")
                self.clear_cache(f"collection_{collection_id}")
            
            # Проверяем кеш
            cache_key = f"collection_{collection_id}"
            if use_cache and self._is_cache_valid(cache_key):
                cached_data = self._cache[cache_key]
                logger.info(f"⚡ Используем кешированную коллекцию")
                cached_data['from_cache'] = True
                return cached_data
            
            # Получаем список документов коллекции
            documents_list = self.get_collection_documents(collection_id)
            
            if not documents_list:
                logger.warning("⚠️ Не удалось получить список документов, используем fallback")
                return self._get_fallback_collection()
            
            logger.info(f"📄 Загружаем контент для {len(documents_list)} документов...")
            
            # Для каждого документа загружаем контент
            loaded_documents = []
            for doc_meta in documents_list:
                doc_id = doc_meta.get('id')
                doc_title = doc_meta.get('title', 'Без названия')
                
                logger.info(f"   📄 Загружаем: {doc_title}")
                
                # Получаем контент документа
                document = self.get_document(doc_id, use_cache=False)
                
                if document:
                    markdown_content = document.get('text', '')
                    
                    # Конвертируем Markdown → HTML на сервере
                    html_content = _markdown_to_html(markdown_content)
                    
                    logger.debug(f"   ✅ Конвертирован: {len(markdown_content)} символов MD → {len(html_content)} символов HTML")
                    
                    loaded_documents.append({
                        'id': doc_id,
                        'title': doc_title,
                        'content': html_content,  # Готовый HTML!
                        'content_markdown': markdown_content,  # Оригинальный MD (на всякий случай)
                        'url': doc_meta.get('url', ''),
                        'icon': _normalize_icon(doc_meta.get('icon')),
                        'color': doc_meta.get('color'),
                        'children': doc_meta.get('children', [])
                    })
                else:
                    logger.warning(f"   ⚠️ Не удалось загрузить: {doc_title}")
            
            logger.info(f"✅ Загружено документов: {len(loaded_documents)}")
            
            # Формируем результат
            result = {
                'title': 'Чеклист поддержки',
                'documents': loaded_documents,
                'from_outline': True,
                'from_cache': False,
                'last_updated': datetime.now().isoformat()
            }
            
            # Сохраняем в кеш
            self._set_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении коллекции: {e}")
            return self._get_fallback_collection()
    
    def _get_fallback_collection(self) -> Dict[str, Any]:
        """Возвращает fallback коллекцию с одним документом"""
        return {
            'title': 'Чеклист для поддержки (офлайн версия)',
            'documents': [
                {
                    'id': 'fallback',
                    'title': 'Чеклист поддержки',
                    'content': DEFAULT_CHECKLIST,
                    'url': '',
                    'icon': None,
                    'color': None,
                    'children': []
                }
            ],
            'from_outline': False,
            'from_cache': False,
            'error': 'Outline недоступен или не настроен'
        }
    
    def get_checklist(self, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Получает чеклист для агентов поддержки
        
        Args:
            use_cache: Использовать ли кеш
            force_refresh: Принудительно обновить из Outline
            
        Returns:
            Словарь с чеклистом:
            {
                'title': str,
                'content': str (markdown),
                'from_outline': bool,
                'last_updated': str (ISO format),
                'error': str (optional)
            }
        """
        try:
            if force_refresh:
                logger.info("🔄 Принудительное обновление чеклиста")
                checklist_id = self.config['checklist_document_id']
                self._clear_cache(checklist_id)
            
            if is_outline_enabled():
                checklist_id = self.config['checklist_document_id']
                document = self.get_document(checklist_id, use_cache=use_cache and not force_refresh)
                
                if document:
                    content = document.get('text', '')
                    logger.info(f"📄 Документ получен из Outline:")
                    logger.info(f"   Заголовок: {document.get('title', 'Без названия')}")
                    logger.info(f"   Размер контента: {len(content)} символов")
                    logger.info(f"   Контент (первые 100 символов): {content[:100]}")
                    
                    if not content or len(content) < 10:
                        logger.warning("⚠️ Контент из Outline пустой, используем fallback")
                        content = DEFAULT_CHECKLIST
                    
                    return {
                        'title': document.get('title', 'Чеклист для поддержки'),
                        'content': content,
                        'from_outline': True,
                        'last_updated': document.get('updatedAt', ''),
                        'from_cache': use_cache and self._is_cache_valid(checklist_id)
                    }
            
            logger.info("📋 Используем fallback чеклист")
            return {
                'title': 'Чеклист для поддержки (офлайн версия)',
                'content': DEFAULT_CHECKLIST,
                'from_outline': False,
                'last_updated': '',
                'from_cache': False,
                'error': 'Outline недоступен или не настроен'
            }
        
        except Exception as e:
            logger.error(f"❌ Ошибка при получении чеклиста: {e}")
            
            return {
                'title': 'Чеклист для поддержки (офлайн версия)',
                'content': DEFAULT_CHECKLIST,
                'from_outline': False,
                'last_updated': '',
                'from_cache': False,
                'error': str(e)
            }


outline_service = OutlineService()

