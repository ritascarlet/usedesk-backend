#!/usr/bin/env python3
"""
Отдельный скрипт для отправки сообщений в Telegram
Запускается как subprocess из основного приложения
"""

import asyncio
import sys
import os
import json
import logging
import time
import re
from datetime import timedelta
from telethon import TelegramClient
from dotenv import load_dotenv
from backend.config.telegram import get_client_config, get_request_config
from urllib.parse import quote

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
PHONE_NUMBER = os.getenv('TELEGRAM_PHONE')

last_request_time = 0
REQUEST_CONFIG = get_request_config()
MIN_REQUEST_INTERVAL = REQUEST_CONFIG['min_interval']

if getattr(sys, 'frozen', False):
    bundle_dir = os.path.dirname(os.path.abspath(sys.executable))
    session_name = os.path.join(bundle_dir, 'admin_session')
else:
    session_name = os.getenv('TELEGRAM_SESSION', 'admin_session')

SESSION_NAME = session_name

TELEGRAM_BOT_USERNAME = "@official_vpnbot"

async def ensure_request_interval():
    """Обеспечивает минимальный интервал между запросами"""
    global last_request_time
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - time_since_last
        logger.info(f"⏱️ Ожидание {sleep_time:.2f} сек для соблюдения интервала запросов")
        await asyncio.sleep(sleep_time)
    
    last_request_time = time.time()

async def send_message_and_get_response(message, use_extended_timeout=False):
    """Отправляет сообщение боту и возвращает ответ
    
    Args:
        message: Текст сообщения для отправки
        use_extended_timeout: Использовать увеличенный таймаут для медленных операций
    """
    client = None
    try:
        # Создаем клиент с оптимизированными настройками для уменьшения flood wait
        client_config = get_client_config()
        client = TelegramClient(
            SESSION_NAME, 
            API_ID, 
            API_HASH,
            **client_config
        )
        
        # Проверяем существование сессии
        session_file = f"{SESSION_NAME}.session"
        if not os.path.exists(session_file):
            logger.info("🔐 Сессия не найдена, требуется авторизация в Telegram")
            print("🔐 Первый запуск - требуется авторизация в Telegram")
            print(f"📱 Номер телефона: {PHONE_NUMBER}")
            
        await client.start(phone=PHONE_NUMBER)
        
        # Обеспечиваем минимальный интервал между запросами
        await ensure_request_interval()
        
        logger.info(f"Отправка сообщения боту {TELEGRAM_BOT_USERNAME}: {message}")
        
        # Отправляем сообщение
        result = await client.send_message(TELEGRAM_BOT_USERNAME, message)
        logger.info(f"Сообщение отправлено: {result.id}")
        
        # Выбираем таймауты в зависимости от типа операции
        if use_extended_timeout:
            max_attempts = REQUEST_CONFIG['extended_max_attempts']
            check_interval = REQUEST_CONFIG['extended_check_interval']
            logger.info(f"⏰ Использован расширенный таймаут: {max_attempts} попыток × {check_interval}с = {max_attempts * check_interval}с")
        else:
            max_attempts = REQUEST_CONFIG['max_attempts']
            check_interval = REQUEST_CONFIG['check_interval']
            logger.info(f"⏰ Использован стандартный таймаут: {max_attempts} попыток × {check_interval}с = {max_attempts * check_interval}с")
        
        # БЫСТРЫЙ опрос с минимальным ожиданием
        logger.info("Быстрый поиск ответа от бота...")
        our_message_time = result.date
        for attempt in range(max_attempts):
            await asyncio.sleep(check_interval)
            
            # Обеспечиваем интервал перед запросом сообщений
            await ensure_request_interval()
            
            # Получаем сообщения с настраиваемым лимитом
            messages = await client.get_messages(TELEGRAM_BOT_USERNAME, limit=REQUEST_CONFIG['message_limit'])
            
            # Ищем новый ответ бота (подписки ИЛИ "нет подписок")
            for msg in messages:
                # Детальное логирование для диагностики
                if not msg.out and msg.text:
                    logger.info(f"🔍 Проверяем сообщение: дата={msg.date}, наша_дата={our_message_time}, новее={(msg.date > our_message_time)}, текст={msg.text[:30]}...")
                    
                # Делаем проверку времени менее строгой (разрешаем сообщения на 5 секунд раньше нашего)
                time_threshold = our_message_time - timedelta(seconds=5)
                if (not msg.out and msg.text and msg.date > time_threshold and 
                    (("**Название:**" in msg.text or "Название:" in msg.text) or
                     ("подписок нет" in msg.text.lower() or "подписки нет" in msg.text.lower() or "нет подписок" in msg.text.lower()) or
                     ("новая подписка успешно добавлена" in msg.text.lower()) or
                     ("вот ваш ключ" in msg.text.lower()))):
                    logger.info(f"⚡ Быстро найден ответ бота (попытка {attempt+1}): {msg.text[:50]}...")
                    return parse_bot_response(msg.text)
            
            # Если нашли любой новый ответ после 1.5 секунд - используем его
            if attempt >= 7:  # После 1.5 секунд
                time_threshold_fallback = our_message_time - timedelta(seconds=5)
                for msg in messages:
                    if not msg.out and msg.text and msg.date > time_threshold_fallback:
                        logger.info(f"Найден любой новый ответ бота (попытка {attempt+1}): {msg.text[:50]}...")
                        return parse_bot_response(msg.text)
        
        # КРИТИЧНО: НЕ ищем старые ответы с подписками, так как они могут быть от других клиентов!
        # Если бот не ответил, возвращаем сообщение о том, что нет ответа
        logger.warning("⚠️ Бот не ответил на запрос в течение таймаута")
        logger.warning("🚨 НЕ используем старые ответы во избежание смешивания данных клиентов!")
        
        # Обеспечиваем интервал перед последним запросом
        await ensure_request_interval()
        
        # Проверяем только последние сообщения после нашего запроса
        messages = await client.get_messages(TELEGRAM_BOT_USERNAME, limit=10)
        
        # Ищем только ответы, которые появились ПОСЛЕ нашего сообщения (с небольшой погрешностью)
        time_threshold = our_message_time - timedelta(seconds=5)
        for msg in messages:
            if (not msg.out and msg.text and msg.date > time_threshold):
                logger.info(f"Найден поздний ответ бота: {msg.text[:50]}...")
                return parse_bot_response(msg.text)
        
        # Если действительно нет ответа - возвращаем ошибку таймаута
        logger.error("🚨 ТАЙМАУТ: Бот не ответил на запрос")
        return "❌ Бот не ответил на запрос в течение таймаута"
        
    except Exception as e:
        error_msg = f"Ошибка отправки сообщения: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"
    
    finally:
        if client and client.is_connected():
            await client.disconnect()

def parse_bot_response(response_text):
    """Парсим ответ бота и извлекаем только названия и сроки"""
    try:
        logger.info(f"Парсинг ответа бота (длина: {len(response_text)}): {response_text[:500]}...")
        
        if "подписок нет" in response_text.lower() or "подписки нет" in response_text.lower() or "нет подписок" in response_text.lower():
            logger.info("🔍 Обнаружен ответ 'Подписок нет'")
            result = {
                "success": True,
                "subscriptions": [],
                "no_subscriptions": True,
                "message": "Подписок нет"
            }
            return json.dumps(result, ensure_ascii=False)
        
        if "**Название:**" not in response_text and "Название:" not in response_text:
            logger.warning("В ответе бота не найдено 'Название:', возвращаем как есть")
            return f"Ответ бота:\n{response_text}"
        
        lines = response_text.strip().split('\n')
        subscriptions = []
        current_subscription = {}
        expect_key_url = False
        expect_uuid = False
        
        for line in lines:
            line = line.strip()
            logger.info(f"🔍 Обрабатываем строку: '{line}'")
            
            if current_subscription and not current_subscription.get('uuid'):
                uuid_pattern_anywhere = r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
                uuid_match = re.search(uuid_pattern_anywhere, line, re.IGNORECASE)
                if uuid_match and not any(keyword in line.lower() for keyword in ['url', 'http', 'proxy', 'vpn']):
                    uuid = uuid_match.group(1)
                    current_subscription['uuid'] = uuid
                    logger.info(f"🎯 Найден отдельно стоящий UUID: {uuid}")
            
            if line.startswith('**Название:**') or line.startswith('Название:'):
                if current_subscription:
                    subscriptions.append(current_subscription)
                    logger.debug(f"Сохранили подписку: {current_subscription}")
                
                if line.startswith('**Название:**'):
                    name = line.replace('**Название:**', '').strip()
                else:
                    name = line.replace('Название:', '').strip()
                
                is_router = bool(re.match(r'^[A-Fa-f0-9]{12}-router$', name, re.IGNORECASE))
                
                current_subscription = {
                    'name': name,
                    'expires': None,
                    'quickinstall': None,
                    'key_url': None,
                    'uuid': None,
                    'is_router': is_router
                }
                logger.debug(f"Начали новую подписку: {current_subscription['name']}")
                expect_key_url = False
                expect_uuid = False
            elif line.startswith('**До:**') or line.startswith('До:') or 'истекает' in line.lower() or 'до:' in line.lower():
                if current_subscription:
                    if line.startswith('**До:**'):
                        expires = line.replace('**До:**', '').strip()
                    elif line.startswith('До:'):
                        expires = line.replace('До:', '').strip()
                    else:
                        date_pattern = r'(\d{1,2}\.\d{1,2}\.\d{2,4})'
                        date_match = re.search(date_pattern, line)
                        if date_match:
                            expires = date_match.group(1)
                        else:
                            expires = line.strip()
                    
                    current_subscription['expires'] = expires
                    logger.info(f"✅ Добавили срок: {current_subscription['expires']}")
            elif line.startswith('**Установить:**') or line.startswith('Установить:'):
                maybe_url = None
                m = re.search(r'\((https?://[^\s)]+)\)', line)
                if m:
                    maybe_url = m.group(1)
                else:
                    m = re.search(r'(https?://\S+)', line)
                    if m:
                        maybe_url = m.group(1)
                if current_subscription and maybe_url:
                    current_subscription['quickinstall'] = maybe_url
                    logger.debug(f"Добавили quickinstall: {maybe_url}")
            elif line.startswith('**Ключ:**') or line.startswith('Ключ:'):
                expect_key_url = True
            elif expect_key_url:
                if line.startswith('http'):
                    current_subscription['key_url'] = line
                    logger.debug(f"Добавили key_url: {line}")
                expect_key_url = False
                if current_subscription.get('key_url') and not current_subscription.get('quickinstall'):
                    encoded = quote(current_subscription['key_url'], safe='')
                    current_subscription['quickinstall'] = f"https://domain.com/choose_device?url={encoded}"
            elif 'id:' in line.lower() or '**id:**' in line.lower():
                logger.info(f"🔍 Найдена строка с ID: '{line}'")
                
                uuid_pattern = r'id:.*?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
                match = re.search(uuid_pattern, line, re.IGNORECASE)
                
                if match:
                    uuid = match.group(1)
                    if current_subscription:
                        current_subscription['uuid'] = uuid
                        logger.info(f"✅ Добавили uuid: {uuid}")
                    else:
                        logger.warning(f"⚠️ UUID найден, но нет активной подписки: {uuid}")
                else:
                    logger.warning(f"⚠️ UUID не найден в строке: {line}")
                    uuid_pattern_any = r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
                    match_any = re.search(uuid_pattern_any, line, re.IGNORECASE)
                    if match_any:
                        uuid = match_any.group(1)
                        if current_subscription:
                            current_subscription['uuid'] = uuid
                            logger.info(f"✅ Найден UUID без префикса id: {uuid}")
                        else:
                            logger.warning(f"⚠️ UUID найден без префикса, но нет активной подписки: {uuid}")
                    else:
                        logger.warning(f"⚠️ UUID вообще не найден в строке: {line}")
        
        if current_subscription:
            subscriptions.append(current_subscription)
            logger.debug(f"Сохранили последнюю подписку: {current_subscription}")
        
        logger.info(f"Найдено подписок: {len(subscriptions)}")
        
        for i, sub in enumerate(subscriptions):
            logger.info(f"📋 Подписка {i+1}:")
            logger.info(f"   Название: {sub.get('name', 'N/A')}")
            logger.info(f"   До: {sub.get('expires', 'N/A')}")
            logger.info(f"   UUID: {sub.get('uuid', 'НЕТ UUID!')}")
            logger.info(f"   Роутер: {sub.get('is_router', False)}")
            logger.info(f"   QuickInstall: {sub.get('quickinstall', 'N/A')}")
        
        if not subscriptions:
            logger.warning("Подписки не найдены после парсинга")
            return f"❌ Подписки не найдены в ответе бота.\n\nПолный ответ:\n{response_text}"
        
        logger.info(f"✅ Итого найдено подписок: {len(subscriptions)}")
        
        result = {
            "success": True,
            "subscriptions": subscriptions
        }
        
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Ошибка парсинга ответа бота: {e}")
        return f"Ответ бота получен, но произошла ошибка парсинга:\n\n{response_text}"

async def main():
    """Главная функция"""
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Неверные аргументы. Использование: python telegram_sender.py 'сообщение'"}))
        sys.exit(1)
    
    message = sys.argv[1]
    
    # Определяем, требуется ли расширенный таймаут
    # Для операций замены ключа нужно больше времени
    use_extended_timeout = message.startswith("Заменить ключ")
    
    try:
        # Отправляем сообщение и получаем ответ
        response = await send_message_and_get_response(message, use_extended_timeout=use_extended_timeout)
        
        # Возвращаем результат в JSON формате
        result = {
            "success": True,
            "response": response
        }
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        # Возвращаем ошибку в JSON формате
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

async def setup_telegram_session():
    """Интерактивная настройка Telegram сессии"""
    client = None
    try:
        logger.info("🔐 Начинаем настройку Telegram авторизации...")
        print("🔐 Настройка Telegram авторизации")
        print(f"📱 Номер телефона: {PHONE_NUMBER}")
        print("📥 Сейчас будет отправлен код подтверждения")
        
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        
        await client.start(phone=PHONE_NUMBER)
        
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info(f"✅ Успешная авторизация: {me.first_name} (@{me.username})")
            print(f"✅ Авторизация успешна: {me.first_name} (@{me.username})")
            print(f"💾 Сессия сохранена: {SESSION_NAME}.session")
            return True
        else:
            logger.error("❌ Ошибка авторизации")
            print("❌ Ошибка авторизации")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка настройки Telegram сессии: {e}")
        print(f"❌ Ошибка: {e}")
        return False
    
    finally:
        if client and client.is_connected():
            await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--setup-auth":
        asyncio.run(setup_telegram_session())
    else:
        asyncio.run(main())