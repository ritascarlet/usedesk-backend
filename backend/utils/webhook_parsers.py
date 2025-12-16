"""
Парсеры для UseDesk webhook данных
Вся логика извлечения данных из UseDesk webhook должна быть здесь!
"""
import logging
from typing import Optional, Dict, Any

from backend.config.constants import (
    USEDESK_TEMPLATE_CLIENT_ID,
    MESSENGER_TYPE_TELEGRAM
)

logger = logging.getLogger(__name__)


def extract_telegram_uid_from_webhook(webhook_data: Dict[str, Any]) -> Optional[str]:
    """
    Извлекает Telegram UID из UseDesk webhook данных.
    Использует многоступенчатую стратегию с приоритетами.
    
    Args:
        webhook_data: Полные данные webhook от UseDesk
        
    Returns:
        Telegram UID как строка или None если не удалось извлечь
        
    Strategy (по приоритету):
        1. contact field (прямой telegram_id)
        2. channel_data.id (если type == 'telegram')
        3. client_data.messengers (поиск telegram messenger)
        4. channel_data.data (fallback)
        5. Извлечение из строки "ID: 123456"
    """
    try:
        logger.debug(f"🔍 ДЕТЕКТИВ: Ищем telegram_uid в webhook")
        
        contact = webhook_data.get('contact')
        if contact:
            telegram_uid = str(contact).strip()
            if telegram_uid and telegram_uid != USEDESK_TEMPLATE_CLIENT_ID:
                logger.info(f"✅ [ПРИОРИТЕТ 1] Найден telegram_uid из contact: {telegram_uid}")
                return telegram_uid
        
        channel_data = webhook_data.get('channel_data', {})
        if channel_data.get('type') == MESSENGER_TYPE_TELEGRAM:
            channel_id = channel_data.get('id')
            if channel_id:
                telegram_uid = str(channel_id).strip()
                if telegram_uid:
                    logger.info(f"✅ [ПРИОРИТЕТ 2] Найден telegram_uid из channel_data.id: {telegram_uid}")
                    return telegram_uid
        
        client_data = webhook_data.get('client_data', {})
        messengers = client_data.get('messengers', [])
        
        for messenger in messengers:
            if messenger.get('type') == MESSENGER_TYPE_TELEGRAM:
                messenger_id = messenger.get('id')
                if messenger_id:
                    messenger_id_str = str(messenger_id).strip()
                    
                    if messenger_id_str.startswith('@'):
                        logger.debug(f"   ⚠️ Messenger ID - это username, не UID: {messenger_id_str}")
                        continue
                    
                    if messenger_id_str.isdigit():
                        logger.info(f"✅ [ПРИОРИТЕТ 3] Найден telegram_uid из messengers: {messenger_id_str}")
                        return messenger_id_str
                    
                    if messenger_id_str.startswith("ID: "):
                        extracted_uid = messenger_id_str.replace("ID: ", "").strip()
                        if extracted_uid.isdigit():
                            logger.info(f"✅ [ПРИОРИТЕТ 3] Извлечен telegram_uid из 'ID: ...' формата: {extracted_uid}")
                            return extracted_uid
        
        if channel_data.get('type') == MESSENGER_TYPE_TELEGRAM:
            channel_data_value = channel_data.get('data')
            if channel_data_value:
                channel_data_str = str(channel_data_value).strip()
                
                if not channel_data_str.startswith('@') and channel_data_str.isdigit():
                    logger.info(f"✅ [ПРИОРИТЕТ 4] Найден telegram_uid из channel_data.data: {channel_data_str}")
                    return channel_data_str
        
        logger.warning(f"❌ ДЕТЕКТИВ ПРОИГРАЛ: Не удалось найти telegram_uid ни одним способом")
        logger.debug(f"   Доступные данные: contact={contact}, channel_data={channel_data}, messengers={messengers}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при извлечении telegram_uid из webhook: {e}", exc_info=True)
        return None


def extract_telegram_username_from_webhook(webhook_data: Dict[str, Any]) -> str:
    """
    Извлекает Telegram username из UseDesk webhook (для отображения).
    
    Args:
        webhook_data: Полные данные webhook от UseDesk
        
    Returns:
        Telegram username или "Неизвестно"
    """
    try:
        client_data = webhook_data.get('client_data', {})
        messengers = client_data.get('messengers', [])
        
        for messenger in messengers:
            if messenger.get('type') == MESSENGER_TYPE_TELEGRAM:
                messenger_id = messenger.get('id', '')
                
                if messenger_id.startswith('@'):
                    return messenger_id
                
                if str(messenger_id).isdigit():
                    return f"ID: {messenger_id}"
        
        channel_data = webhook_data.get('channel_data', {})
        if channel_data.get('type') == MESSENGER_TYPE_TELEGRAM:
            channel_data_value = channel_data.get('data')
            if channel_data_value:
                if str(channel_data_value).startswith('@'):
                    return str(channel_data_value)
                else:
                    return f"ID: {channel_data_value}"
        
        return "Неизвестно"
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении telegram username: {e}")
        return "Неизвестно"


def extract_client_name_from_webhook(webhook_data: Dict[str, Any]) -> str:
    """
    Извлекает имя клиента из UseDesk webhook.
    
    Args:
        webhook_data: Полные данные webhook от UseDesk
        
    Returns:
        Имя клиента или "Неизвестно"
    """
    try:
        client_data = webhook_data.get('client_data', {})
        name = client_data.get('name', 'Неизвестно')
        return name if name else 'Неизвестно'
    except Exception as e:
        logger.error(f"Ошибка при извлечении имени клиента: {e}")
        return "Неизвестно"


def extract_client_id_from_webhook(webhook_data: Dict[str, Any], url_client_id: Optional[str] = None) -> Optional[str]:
    """
    Извлекает client_id из UseDesk webhook с поддержкой fallback стратегий.
    
    Args:
        webhook_data: Полные данные webhook от UseDesk
        url_client_id: client_id из URL параметров (может быть шаблоном {{client_id}})
        
    Returns:
        client_id или None если не удалось извлечь
        
    Strategy:
        1. Используем url_client_id если он валидный (не шаблон)
        2. webhook_data.client_id
        3. webhook_data.contact (как fallback)
    """
    try:
        if url_client_id and url_client_id != USEDESK_TEMPLATE_CLIENT_ID:
            logger.debug(f"✅ Используем client_id из URL: {url_client_id}")
            return url_client_id
        
        client_id = webhook_data.get('client_id')
        if client_id and str(client_id) != USEDESK_TEMPLATE_CLIENT_ID:
            logger.debug(f"✅ Используем client_id из webhook: {client_id}")
            return str(client_id)
        
        contact = webhook_data.get('contact')
        if contact:
            logger.warning(f"⚠️ Fallback: используем contact как client_id: {contact}")
            return str(contact)
        
        logger.error(f"❌ Не удалось извлечь client_id ни одним способом")
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при извлечении client_id: {e}")
        return None


def validate_webhook_data(webhook_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Валидирует данные webhook от UseDesk.
    
    Args:
        webhook_data: Данные webhook
        
    Returns:
        (is_valid, error_message) - кортеж с результатом валидации
    """
    if not webhook_data:
        return False, "Webhook данные пустые"
    
    if not isinstance(webhook_data, dict):
        return False, "Webhook данные не являются словарем"
    
    required_fields = ['client_id', 'channel_data']
    missing_fields = [field for field in required_fields if field not in webhook_data]
    
    if missing_fields:
        return False, f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
    
    channel_data = webhook_data.get('channel_data', {})
    if channel_data.get('type') != MESSENGER_TYPE_TELEGRAM:
        return False, f"Неподдерживаемый тип канала: {channel_data.get('type')}"
    
    return True, ""

