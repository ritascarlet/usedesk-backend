"""
Утилиты для парсинга ответов от Telegram бота
"""
import json
import re
import logging
from typing import Optional, Dict, Any

from backend.config.constants import (
    ROUTER_KEYWORDS,
    SUBSCRIPTION_TYPE_ROUTER,
    SUBSCRIPTION_TYPE_CLIENT,
    QUICKINSTALL_URL_PATTERN,
    TELEGRAM_UID_PATTERN
)

logger = logging.getLogger(__name__)


def parse_telegram_bot_response(response_text: str) -> Dict[str, Any] | str:
    """
    Универсальный парсер ответов от Telegram бота.
    Обрабатывает "двойной JSON" и другие edge cases.
    
    Args:
        response_text: Текст ответа от бота (может быть JSON или plain text)
        
    Returns:
        Распарсенный JSON dict или оригинальную строку если парсинг не удался
    """
    if not response_text:
        return response_text
    
    if isinstance(response_text, dict):
        return response_text
    
    try:
        parsed = json.loads(response_text)
        
        if isinstance(parsed, dict) and 'response' in parsed:
            response_field = parsed['response']
            
            if isinstance(response_field, str):
                try:
                    logger.debug("Обнаружен 'двойной JSON', делаем второй парсинг")
                    nested_parsed = json.loads(response_field)
                    
                    if isinstance(nested_parsed, dict):
                        return nested_parsed
                except json.JSONDecodeError:
                    pass
        
        return parsed
        
    except json.JSONDecodeError:
        logger.debug(f"Не удалось распарсить как JSON: {response_text[:100]}")
        return response_text
    except Exception as e:
        logger.error(f"Неожиданная ошибка при парсинге ответа: {e}")
        return response_text


def parse_replace_response(response_text: str) -> Optional[str]:
    """
    Парсит ответ бота после замены ключа и извлекает новый quickinstall
    
    Args:
        response_text: Текст ответа от бота
        
    Returns:
        URL нового quickinstall или None если не удалось извлечь
    """
    try:
        logger.info(f"Парсинг ответа замены ключа (первые 200 символов): {response_text[:200]}")
        
        response_data = parse_telegram_bot_response(response_text)
        
        if isinstance(response_data, dict):
            if response_data.get('success') and 'subscriptions' in response_data:
                subscriptions = response_data['subscriptions']
                if subscriptions and len(subscriptions) > 0:
                    quickinstall = subscriptions[0].get('quickinstall')
                    if quickinstall:
                        logger.info(f"✅ Найден quickinstall из JSON: {quickinstall}")
                        return quickinstall
        
        text_to_search = response_text if isinstance(response_text, str) else str(response_data)
        match = re.search(QUICKINSTALL_URL_PATTERN, text_to_search)
        
        if match:
            quickinstall = match.group(0)
            logger.info(f"✅ Найден quickinstall через regex: {quickinstall}")
            return quickinstall
        
        if isinstance(text_to_search, str) and "Новая подписка успешно добавлена" in text_to_search:
            logger.info(f"✅ Замена ключа успешна! Бот подтвердил: '{text_to_search[:100]}'")
            logger.info(f"   Возвращаем специальный маркер для обновления подписок")
            return "SUCCESS_BUT_NO_URL"
        
        logger.warning(f"⚠️ Не удалось извлечь quickinstall из ответа")
        logger.debug(f"   Полный ответ: {text_to_search[:500]}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге ответа замены ключа: {e}")
        return None


def is_router_subscription(name: str) -> bool:
    """
    Проверяет является ли подписка роутерной
    
    Args:
        name: Название подписки
        
    Returns:
        True если это роутерная подписка, иначе False
    """
    if not name:
        return False
    
    name_lower = name.lower()
    
    return any(keyword in name_lower for keyword in ROUTER_KEYWORDS)


def get_subscription_type(name: str) -> str:
    """
    Определяет тип подписки по названию
    
    Args:
        name: Название подписки
        
    Returns:
        SUBSCRIPTION_TYPE_ROUTER если роутерная подписка
        SUBSCRIPTION_TYPE_CLIENT если обычная подписка
    """
    return SUBSCRIPTION_TYPE_ROUTER if is_router_subscription(name) else SUBSCRIPTION_TYPE_CLIENT


def parse_telegram_uid(contact: str | int) -> Optional[str]:
    """
    Извлекает Telegram UID из различных форматов
    
    Args:
        contact: Контактные данные (может быть строкой или числом)
        
    Returns:
        Telegram UID как строка или None
    """
    try:
        if not contact:
            return None
        
        contact_str = str(contact).strip()
        
        if contact_str.startswith('@'):
            contact_str = contact_str[1:]
        
        if re.match(TELEGRAM_UID_PATTERN, contact_str):
            return contact_str
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при парсинге Telegram UID: {e}")
        return None

