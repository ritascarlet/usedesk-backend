"""
Утилиты для работы с подписками
"""
import logging
from urllib.parse import quote
from backend.utils.date_utils import get_days_left, get_subscription_status, format_days_left, get_status_text
from backend.utils.parsers import get_subscription_type, is_router_subscription

logger = logging.getLogger(__name__)


def process_subscription(subscription: dict) -> dict:
    """
    Обрабатывает данные одной подписки и добавляет дополнительные поля
    
    Args:
        subscription: Словарь с данными подписки
        
    Returns:
        Обработанный словарь подписки с дополнительными полями
    """
    name = subscription.get('name', '')
    expires = subscription.get('expires', '')
    quickinstall = subscription.get('quickinstall', '')
    
    days_left = get_days_left(expires)
    
    status = get_subscription_status(expires)
    
    days_left_short, days_left_text = format_days_left(days_left)
    
    sub_type = get_subscription_type(name)
    
    status_text = get_status_text(status)
    
    quickinstall_encoded = quote(quickinstall, safe='') if quickinstall else None
    
    processed = subscription.copy()
    processed.update({
        'status': status,
        'type': sub_type,
        'days_left_short': days_left_short,
        'days_left_text': days_left_text,
        'quickinstall_encoded': quickinstall_encoded,
        'status_text': status_text,
        'is_router': is_router_subscription(name)
    })
    
    return processed


def process_subscriptions_list(subscriptions: list) -> list:
    """
    Обрабатывает список подписок
    
    Args:
        subscriptions: Список словарей с подписками
        
    Returns:
        Обработанный список подписок
    """
    if not subscriptions:
        return []
    
    return [process_subscription(sub) for sub in subscriptions]


def sort_subscriptions(subscriptions: list, sort_by: str = 'status') -> list:
    """
    Сортирует подписки
    
    Args:
        subscriptions: Список подписок
        sort_by: Поле для сортировки ('status', 'name', 'expires')
        
    Returns:
        Отсортированный список подписок
    """
    if not subscriptions:
        return []
    
    if sort_by == 'status':
        status_order = {'active': 1, 'expiring': 2, 'expired': 3, 'unknown': 4}
        return sorted(subscriptions, key=lambda x: status_order.get(x.get('status', 'unknown'), 4))
    
    elif sort_by == 'name':
        return sorted(subscriptions, key=lambda x: (not x.get('is_router', False), x.get('name', '')))
    
    elif sort_by == 'expires':
        return sorted(subscriptions, key=lambda x: x.get('expires', ''), reverse=True)
    
    return subscriptions

