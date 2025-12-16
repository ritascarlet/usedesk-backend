"""
Конфигурация для Outline API
"""
import os
from dotenv import load_dotenv

load_dotenv()


OUTLINE_BASE_URL = os.getenv('OUTLINE_BASE_URL', 'https://domain.com')

OUTLINE_API_TOKEN = os.getenv('OUTLINE_API_TOKEN', '')

OUTLINE_COLLECTION_ID = os.getenv('OUTLINE_COLLECTION_ID', '')

OUTLINE_CHECKLIST_DOCUMENT_ID = os.getenv('OUTLINE_CHECKLIST_DOCUMENT_ID', '')


OUTLINE_CACHE_TTL = int(os.getenv('OUTLINE_CACHE_TTL', '300'))


OUTLINE_REQUEST_TIMEOUT = int(os.getenv('OUTLINE_REQUEST_TIMEOUT', '10'))

OUTLINE_MAX_RETRIES = int(os.getenv('OUTLINE_MAX_RETRIES', '3'))


DEFAULT_CHECKLIST = """


- [ ] Проверить статус подписки клиента
- [ ] Уточнить детали проблемы у клиента
- [ ] Проверить историю обращений


- [ ] Предложить продление подписки
- [ ] Объяснить процесс оплаты
- [ ] Отправить ссылку на оплату

- [ ] Проверить правильность подключения
- [ ] Предложить замену ключа (кнопка в модуле)
- [ ] Убедиться что клиент использует актуальную версию приложения

- [ ] **НЕ МЕНЯТЬ КЛЮЧИ** для router подписок
- [ ] Дать инструкцию по настройке роутера
- [ ] Проверить совместимость роутера


- [ ] Отправить quickinstall ссылку клиенту
- [ ] Убедиться что клиент все понял
- [ ] Попросить клиента подтвердить решение проблемы
- [ ] Закрыть тикет с кратким резюме


- Документация: https://domain.com/docs
- FAQ: https://domain.com/faq
- Инструкции: https://domain.com/help
"""

# ========== ВАЛИДАЦИЯ КОНФИГУРАЦИИ ==========

def validate_outline_config():
    """Проверяет наличие обязательных настроек Outline"""
    if not OUTLINE_API_TOKEN:
        return False, "OUTLINE_API_TOKEN не установлен"
    
    if not OUTLINE_COLLECTION_ID and not OUTLINE_CHECKLIST_DOCUMENT_ID:
        return False, "Не установлен ни OUTLINE_COLLECTION_ID, ни OUTLINE_CHECKLIST_DOCUMENT_ID"
    
    if not OUTLINE_BASE_URL or OUTLINE_BASE_URL == 'https://domain.com':
        return False, "OUTLINE_BASE_URL не установлен или использует значение по умолчанию"
    
    return True, "Outline конфигурация валидна"


def is_outline_enabled():
    """Проверяет, включена ли интеграция с Outline"""
    is_valid, _ = validate_outline_config()
    return is_valid


def get_outline_config():
    """Возвращает конфигурацию Outline для использования в сервисах"""
    return {
        'base_url': OUTLINE_BASE_URL,
        'api_token': OUTLINE_API_TOKEN,
        'collection_id': OUTLINE_COLLECTION_ID,
        'checklist_document_id': OUTLINE_CHECKLIST_DOCUMENT_ID,
        'cache_ttl': OUTLINE_CACHE_TTL,
        'request_timeout': OUTLINE_REQUEST_TIMEOUT,
        'max_retries': OUTLINE_MAX_RETRIES,
    }

