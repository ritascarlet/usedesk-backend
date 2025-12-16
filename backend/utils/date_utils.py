"""
Утилиты для работы с датами и подписками
"""
from datetime import datetime
from dateutil import parser as date_parser
import logging

from backend.config.constants import (
    SUBSCRIPTION_EXPIRING_THRESHOLD_DAYS,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_EXPIRING,
    SUBSCRIPTION_STATUS_EXPIRED,
    SUBSCRIPTION_STATUS_UNKNOWN,
    DAYS_LEFT_TODAY,
    DAYS_LEFT_TOMORROW,
    DAYS_LEFT_UNKNOWN
)

logger = logging.getLogger(__name__)


def get_days_left(expires_date: str) -> int | None:
    """
    Рассчитывает количество дней до истечения подписки
    
    Args:
        expires_date: Дата истечения в формате DD.MM.YY, DD.MM.YYYY или другом распознаваемом формате
        
    Returns:
        Количество дней до истечения (может быть отрицательным если истекла)
        или None если дата невалидна
    """
    try:
        if not expires_date:
            return None
        
        expire_date = date_parser.parse(expires_date, dayfirst=True)
        today = datetime.now()
        
        expire_date = expire_date.replace(hour=0, minute=0, second=0, microsecond=0)
        today = today.replace(hour=0, minute=0, second=0, microsecond=0)
        
        delta = expire_date - today
        return delta.days
        
    except Exception as e:
        logger.error(f"Ошибка парсинга даты {expires_date}: {e}")
        return None


def get_subscription_status(expires_date: str, expiring_threshold: int = SUBSCRIPTION_EXPIRING_THRESHOLD_DAYS) -> str:
    """
    Определяет статус подписки на основе даты истечения
    
    Args:
        expires_date: Дата истечения в формате DD.MM.YY, DD.MM.YYYY или другом
        expiring_threshold: Количество дней до истечения для статуса "expiring"
        
    Returns:
        SUBSCRIPTION_STATUS_ACTIVE - подписка активна (больше expiring_threshold дней)
        SUBSCRIPTION_STATUS_EXPIRING - подписка скоро истечет (меньше expiring_threshold дней)
        SUBSCRIPTION_STATUS_EXPIRED - подписка истекла
        SUBSCRIPTION_STATUS_UNKNOWN - не удалось определить статус
    """
    days_left = get_days_left(expires_date)
    
    if days_left is None:
        return SUBSCRIPTION_STATUS_UNKNOWN
    
    if days_left < 0:
        return SUBSCRIPTION_STATUS_EXPIRED
    elif days_left <= expiring_threshold:
        return SUBSCRIPTION_STATUS_EXPIRING
    else:
        return SUBSCRIPTION_STATUS_ACTIVE


def format_days_left(days_left: int | None) -> tuple[str, str]:
    """
    Форматирует количество оставшихся дней
    
    Args:
        days_left: Количество дней
        
    Returns:
        Кортеж (короткая_форма, длинная_форма)
        Например: ('15д', 'через 15 дн.')
    """
    if days_left is None:
        return ('?', DAYS_LEFT_UNKNOWN)
    
    if days_left < 0:
        abs_days = abs(days_left)
        short = f"-{abs_days}д"
        long = f"истек {abs_days} дн. назад"
    elif days_left == 0:
        short = DAYS_LEFT_TODAY
        long = f"истекает {DAYS_LEFT_TODAY}"
    elif days_left == 1:
        short = DAYS_LEFT_TOMORROW
        long = f"истекает {DAYS_LEFT_TOMORROW}"
    else:
        short = f"{days_left}д"
        long = f"через {days_left} дн."
    
    return (short, long)


def get_status_text(status: str) -> str:
    """
    Возвращает текстовое представление статуса подписки
    
    Args:
        status: Статус (SUBSCRIPTION_STATUS_*)
        
    Returns:
        Текстовое описание статуса
    """
    status_map = {
        SUBSCRIPTION_STATUS_ACTIVE: 'Активна',
        SUBSCRIPTION_STATUS_EXPIRING: 'Скоро',
        SUBSCRIPTION_STATUS_EXPIRED: 'Истекла',
        SUBSCRIPTION_STATUS_UNKNOWN: 'Неизвестно'
    }
    
    return status_map.get(status, 'Неизвестно')

