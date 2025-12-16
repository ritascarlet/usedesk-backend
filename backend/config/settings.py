"""
Конфигурация приложения UseDesk Backend
"""
import os
from dotenv import load_dotenv

load_dotenv()


APP_VERSION = "2.1"

SECURITY_HASH = os.getenv(
    'SECURITY_HASH',
    "change_me_security_hash_for_public_release"
)


TELEGRAM_BOT_USERNAME = "@official_vpnbot"

TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')
TELEGRAM_SESSION = os.getenv('TELEGRAM_SESSION', 'admin_session')


CACHE_DIR = os.getenv('CACHE_DIR', '/app/cache')

CACHE_TIMEOUT = 300


TELEGRAM_SUBPROCESS_TIMEOUT = 15

TELEGRAM_REPLACE_KEY_TIMEOUT = 60


DEBUG_MODE = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))


LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


SUBSCRIPTION_EXPIRING_DAYS = 14


REMNA_API_DOMAIN = os.getenv('REMNA_API_DOMAIN', 'domain.com')
REMNA_API_TOKEN = os.getenv('REMNA_API_TOKEN')


def validate_config():
    """Проверяет наличие обязательных переменных окружения"""
    required_vars = [
        'TELEGRAM_API_ID',
        'TELEGRAM_API_HASH',
        'TELEGRAM_PHONE',
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        raise ValueError(
            f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
        )
    
    return True

# ========== ВЫВОД НАСТРОЕК ПРИ ЗАПУСКЕ ==========

def print_config():
    """Выводит текущие настройки при запуске"""
    masked_hash = (
        f"{SECURITY_HASH[:4]}...{SECURITY_HASH[-4:]}"
        if SECURITY_HASH and len(SECURITY_HASH) > 8
        else "not_set"
    )
    print(f"🔧 SECURITY_HASH (masked): {masked_hash}")
    print(f"🔧 Длина SECURITY_HASH: {len(SECURITY_HASH)}")
    print(f"🔧 Версия {APP_VERSION}")

