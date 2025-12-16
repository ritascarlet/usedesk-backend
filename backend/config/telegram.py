#!/usr/bin/env python3
"""
Дополнительные настройки для оптимизации Telegram API
"""

TELEGRAM_CONFIG = {
    'flood_sleep_threshold': 60,
    'request_retries': 5,
    'retry_delay': 2,
    
    'min_request_interval': 1.0,
    'message_check_interval': 0.5,
    'max_message_attempts': 6,
    
    'extended_check_interval': 1.0,
    'extended_max_attempts': 20,
    
    'message_limit': 8,
    'max_message_limit': 10,
    
    'connection_timeout': 30,
    'request_timeout': 60,
}

def get_client_config():
    """Возвращает настройки для создания Telegram клиента"""
    return {
        'flood_sleep_threshold': TELEGRAM_CONFIG['flood_sleep_threshold'],
        'request_retries': TELEGRAM_CONFIG['request_retries'],
        'retry_delay': TELEGRAM_CONFIG['retry_delay'],
        'connection_retries': 3,
        'auto_reconnect': True,
        'timeout': TELEGRAM_CONFIG['connection_timeout'],
    }

# Функция для получения настроек запросов
def get_request_config():
    """Возвращает настройки для запросов"""
    return {
        'min_interval': TELEGRAM_CONFIG['min_request_interval'],
        'check_interval': TELEGRAM_CONFIG['message_check_interval'],
        'max_attempts': TELEGRAM_CONFIG['max_message_attempts'],
        'extended_check_interval': TELEGRAM_CONFIG['extended_check_interval'],
        'extended_max_attempts': TELEGRAM_CONFIG['extended_max_attempts'],
        'message_limit': TELEGRAM_CONFIG['message_limit'],
        'max_message_limit': TELEGRAM_CONFIG['max_message_limit'],
    }

