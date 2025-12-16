"""
Сервис для работы с Telegram
Обертка над telegram_sender.py для удобного использования в приложении
"""
import subprocess
import logging
import sys
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from backend.config.settings import TELEGRAM_SUBPROCESS_TIMEOUT, TELEGRAM_REPLACE_KEY_TIMEOUT
from backend.config.constants import (
    TELEGRAM_MAX_RETRY_ATTEMPTS,
    TELEGRAM_RETRY_MIN_WAIT,
    TELEGRAM_RETRY_MAX_WAIT
)

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(TELEGRAM_MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=TELEGRAM_RETRY_MIN_WAIT, max=TELEGRAM_RETRY_MAX_WAIT),
    retry=retry_if_exception_type((subprocess.SubprocessError, ConnectionError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def send_message_to_bot(message: str, timeout: int = None) -> str:
    """
    Отправляет сообщение боту через subprocess с автоматическими повторами
    
    Args:
        message: Текст сообщения для отправки
        timeout: Таймаут ожидания ответа (по умолчанию TELEGRAM_SUBPROCESS_TIMEOUT)
        
    Returns:
        Ответ от бота или сообщение об ошибке
        
    Raises:
        subprocess.SubprocessError: При фатальной ошибке subprocess после всех повторов
        subprocess.TimeoutExpired: При таймауте (не повторяется)
    """
    actual_timeout = timeout if timeout is not None else TELEGRAM_SUBPROCESS_TIMEOUT
    
    try:
        logger.info(f"📤 Отправка сообщения боту: {message[:50]}{'...' if len(message) > 50 else ''}")
        logger.info(f"⏱️ Таймаут ожидания: {actual_timeout}s")
        logger.debug("🔄 Режим Python: запуск через subprocess")
        
        python_executable = sys.executable
        
        result = subprocess.run(
            [python_executable, '-m', 'backend.services.telegram_sender', message],
            capture_output=True,
            text=True,
            timeout=actual_timeout,
            check=False
        )
        
        if result.returncode != 0:
            error_msg = f"❌ Ошибка subprocess (код {result.returncode}): {result.stderr}"
            logger.error(error_msg)
            raise subprocess.SubprocessError(error_msg)
        
        logger.info("✅ Сообщение успешно отправлено через subprocess")
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"⏱️ Timeout при отправке сообщения через subprocess ({actual_timeout}s)")
        return f"❌ Timeout: Слишком долго ждем ответ от бота ({actual_timeout}s)"
    
    except Exception as e:
        error_msg = f"Ошибка subprocess: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return f"❌ {error_msg}"


def send_get_subscriptions_command(telegram_uid: str) -> str:
    """
    Отправляет команду для получения подписок пользователя
    
    Args:
        telegram_uid: Telegram UID пользователя
        
    Returns:
        Ответ от бота с подписками
    """
    message = f"Узнать подписки\n{telegram_uid}"
    return send_message_to_bot(message)


def send_replace_key_command(telegram_uid: str, uuid: str) -> str:
    """
    Отправляет команду для замены ключа подписки.
    Использует увеличенный timeout, т.к. бот отправляет 2 сообщения:
    1. "Новая подписка успешно добавлена!"
    2. "Вот ваш ключ: ..."
    
    Args:
        telegram_uid: Telegram UID пользователя
        uuid: UUID подписки для замены
        
    Returns:
        Ответ от бота с новым ключом
    """
    message = f"Заменить ключ\n{telegram_uid}\n{uuid}"
    logger.info(f"🔄 Отправка команды замены ключа боту")
    logger.info(f"   UID: {telegram_uid}, UUID: {uuid}")
    logger.info(f"   Ожидаем ответ до {TELEGRAM_REPLACE_KEY_TIMEOUT}s (бот отправляет 2 сообщения)")
    return send_message_to_bot(message, timeout=TELEGRAM_REPLACE_KEY_TIMEOUT)

