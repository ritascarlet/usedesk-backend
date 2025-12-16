"""
UseDesk endpoints - основные endpoints для интеграции с UseDesk
"""
import time
import json
import logging
from flask import Blueprint, request, jsonify, render_template, make_response
from urllib.parse import quote

from backend.config.settings import SECURITY_HASH
from backend.services.telegram_service import send_message_to_bot, send_replace_key_command
from backend.utils import (
    process_subscriptions_list,
    sort_subscriptions,
    parse_replace_response,
    parse_telegram_bot_response,
    is_router_subscription,
    extract_telegram_uid_from_webhook,
    extract_telegram_username_from_webhook,
    extract_client_name_from_webhook,
    extract_client_id_from_webhook,
    validate_webhook_data
)
from backend.config.constants import (
    SUBSCRIPTION_CRITICAL_THRESHOLD_DAYS
)

logger = logging.getLogger(__name__)

usedesk_bp = Blueprint('usedesk', __name__)


@usedesk_bp.route(f'/{SECURITY_HASH}_useDeskGetUserConfigs', methods=['GET', 'POST'])
def get_user_configs():
    """Эндпоинт для получения конфигураций пользователя через UseDesk API и Telegram"""
    print(f"🎯 ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_useDeskGetUserConfigs")
    logger.info(f"🎯 ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_useDeskGetUserConfigs")
    logger.info(f"🎯 Метод запроса: {request.method}")
    logger.info(f"🎯 URL: {request.url}")
    
    try:
        # Метрики производительности
        start_time = time.time()
        
        # Логируем детали запроса для отладки
        logger.info(f"=== ВХОДЯЩИЙ ЗАПРОС ===")
        logger.info(f"Метод: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"URL параметры: {dict(request.args)}")
        logger.info(f"Заголовки: {dict(request.headers)}")
        
        if request.method == 'POST':
            post_data = request.get_json()
            logger.info(f"JSON тело: {post_data}")
        else:
            post_data = {}
        
        # Поддерживаем client_id как из URL параметров (GET), так и из тела запроса (POST)
        client_id = request.args.get('client_id')  # Из URL
        if not client_id and request.method == 'POST':
            client_id = post_data.get('client_id') if post_data else None  # Из JSON тела

        # Параметр для принудительного обновления без кеша
        refresh_value = request.args.get('refresh') or (post_data.get('refresh') if post_data else None)
        refresh_requested = str(refresh_value).lower() in ('1', 'true', 'yes', 'y') if refresh_value is not None else False
        
        # UseDesk webhook может отправлять незаполненный шаблон {{client_id}}
        # ДЕТЕКТИВ ФУНКЦИЯ: ищем правильный client_id любыми способами!
        if client_id == '{{client_id}}' and request.method == 'POST' and post_data:
            logger.info(f"🔍 ДЕТЕКТИВ РЕЖИМ: UseDesk послал шаблон, ищем настоящий client_id!")
            
            # СПОСОБ 1: Пробуем contact
            contact_id = post_data.get('contact')
            ticket_id = post_data.get('ticket_id')
            
            logger.info(f"🔍 Найдено в webhook: contact={contact_id}, ticket_id={ticket_id}")
            
            # СПОСОБ 2: Если ничего не нашли, используем contact как fallback
            if client_id == '{{client_id}}' and contact_id:
                logger.info(f"🔄 Fallback: используем contact как client_id: {contact_id}")
                client_id = contact_id
            
            # СПОСОБ 3: Поиск по telegram username (экстремальный режим)
            if client_id == '{{client_id}}':
                client_data = post_data.get('client_data', {})
                messengers = client_data.get('messengers', [])
                for messenger in messengers:
                    if messenger.get('type') == 'telegram':
                        tg_username = messenger.get('id', '')
                        logger.info(f"🚀 ЭКСТРЕМАЛЬНЫЙ РЕЖИМ: пробуем поиск по telegram {tg_username}")
                        break
            
            if client_id != '{{client_id}}':
                logger.info(f"🏆 ДЕТЕКТИВ ПОБЕДИЛ! Найден client_id: {client_id}")
            else:
                logger.error(f"💀 ДЕТЕКТИВ ПРОИГРАЛ! Не смогли найти client_id")
        
        logger.info(f"Финальный client_id: {client_id}")
        
        if not client_id or client_id == '{{client_id}}':
            return jsonify({"error": "Параметр client_id обязателен и не должен быть шаблоном (в URL или JSON)"}), 400
        
        # РЕФАКТОРИНГ: Используем новые утилиты для извлечения данных
        logger.info(f"🎣 Обрабатываем UseDesk webhook для client_id: {client_id}")
        
        # Валидируем webhook данные
        is_valid, error_message = validate_webhook_data(post_data)
        if not is_valid:
            logger.error(f"❌ Невалидный webhook: {error_message}")
            return jsonify({"error": f"Невалидные webhook данные: {error_message}"}), 400
        
        # Извлекаем данные через утилиты (вместо ~70 строк хардкода!)
        telegram_uid = extract_telegram_uid_from_webhook(post_data)
        telegram_username = extract_telegram_username_from_webhook(post_data)
        client_name = extract_client_name_from_webhook(post_data)
        
        logger.info(f"📋 Извлечены данные: имя='{client_name}', username='{telegram_username}', uid='{telegram_uid}'")
        
        # Проверяем что у нас есть Telegram UID для запроса к боту
        if not telegram_uid:
            error_msg = f"Telegram UID не найден в webhook'е для клиента {client_id}"
            logger.error(error_msg)
            logger.debug(f"   Webhook data: {post_data}")
            return jsonify({"error": error_msg}), 400
        
        logger.info(f"✅ Найден Telegram UID: {telegram_uid} для пользователя {telegram_username}")
        
        # Шаг 3: Отправляем запрос в Telegram бота с UID (на двух строках)
        telegram_message = f"Узнать подписки\n{telegram_uid}"
        logger.info(f"Отправка запроса в Telegram: {repr(telegram_message)}")
        
        # Проверяем кеш сначала
        from backend.core.cache_manager import bot_cache
        cached_data = bot_cache.get(client_id, telegram_uid) if not refresh_requested else None
        from_cache = False
        no_subscriptions_message = None
        
        if cached_data:
            logger.info("⚡ Используем кешированные данные")
            from_cache = True
            # Проверяем, это обычные данные или специальный случай отсутствия подписок
            if isinstance(cached_data, dict) and cached_data.get('no_subscriptions'):
                subscriptions_data = []
                no_subscriptions_message = cached_data.get('message', 'Подписок нет')
                logger.info(f"📭 Из кеша: {no_subscriptions_message}")
                # Извлекаем сохраненное имя клиента
                if 'client_name' in cached_data:
                    client_name = cached_data['client_name']
            elif isinstance(cached_data, dict) and 'subscriptions' in cached_data:
                subscriptions_data = cached_data['subscriptions']
                # Извлекаем сохраненное имя клиента
                if 'client_name' in cached_data:
                    client_name = cached_data['client_name']
            else:
                # Старый формат кеша - просто массив подписок
                subscriptions_data = cached_data if isinstance(cached_data, list) else []
        else:
            # БЫСТРЫЙ СИНХРОННЫЙ ЗАПРОС
            logger.info("🚀 Быстрый запрос к боту...")
            bot_response = send_message_to_bot(telegram_message)
            
            # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ОТВЕТА ОТ БОТА
            logger.info(f"🤖 ОТВЕТ ОТ TELEGRAM БОТА:")
            logger.info(f"   Тип ответа: {type(bot_response)}")
            logger.info(f"   Длина ответа: {len(str(bot_response)) if bot_response else 0}")
            logger.info(f"   Ответ (первые 200 символов): {str(bot_response)[:200] if bot_response else 'ПУСТОЙ'}")
            
            # Проверяем, что получены корректные данные
            if not bot_response or bot_response.startswith("❌"):
                logger.error(f"❌ Некорректный ответ от бота: {bot_response}")
                
                # Специальная обработка для таймаута
                if "таймаута" in bot_response.lower():
                    logger.warning("⏰ Бот не ответил в течение таймаута - возможно, у клиента нет подписок")
                    # Возвращаем пустой результат вместо ошибки
                    subscriptions_data = []
                    no_subscriptions_message = "Бот не ответил (возможно, подписок нет)"
                else:
                    return jsonify({"error": "Не удалось получить данные о подписках"}), 500
            else:
                # Парсим ответ используя универсальный парсер (обрабатывает двойной JSON автоматически!)
                subscriptions_data = []
                no_subscriptions_message = None
                try:
                    logger.info(f"📋 Парсим ответ от бота...")
                    response_json = parse_telegram_bot_response(bot_response)
                    logger.info(f"✅ Ответ распарсен: {type(response_json)}")
                    
                    # Если парсер вернул dict - обрабатываем как JSON
                    if isinstance(response_json, dict) and response_json.get('success'):
                        if response_json.get('no_subscriptions'):
                            # Случай отсутствия подписок
                            logger.info("📭 Обнаружен случай отсутствия подписок")
                            subscriptions_data = []
                            no_subscriptions_message = response_json.get('message', 'Подписок нет')
                            # Сохраняем в кеш пустой массив с флагом
                            try:
                                cache_data = {
                                    'subscriptions': [],
                                    'no_subscriptions': True,
                                    'message': no_subscriptions_message,
                                    'client_name': client_name,
                                    'timestamp': time.time()
                                }
                                bot_cache.set(client_id, telegram_uid, cache_data)
                                logger.info("💾 Данные 'no_subscriptions' с именем клиента сохранены в кеш")
                            except Exception as cache_error:
                                logger.error(f"❌ Ошибка сохранения 'no_subscriptions' в кеш: {cache_error}")
                        elif 'subscriptions' in response_json:
                            subscriptions_data = response_json['subscriptions']
                            logger.info(f"✅ Найдено подписок: {len(subscriptions_data)}")
                            logger.info(f"📋 Подписки: {subscriptions_data}")
                            # Сохраняем в кеш
                            try:
                                cache_data = {
                                    'subscriptions': subscriptions_data,
                                    'client_name': client_name,
                                    'timestamp': time.time()
                                }
                                bot_cache.set(client_id, telegram_uid, cache_data)
                                logger.info("💾 Данные с именем клиента сохранены в кеш")
                            except Exception as cache_error:
                                logger.error(f"❌ Ошибка сохранения в кеш: {cache_error}")
                        else:
                            logger.warning(f"⚠️ JSON не содержит подписок или флага no_subscriptions")
                    else:
                        logger.warning(f"⚠️ JSON success=False")
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга JSON: {e}")
                    logger.error(f"❌ Сырой ответ: {bot_response}")
                    subscriptions_data = []
        
        remnawave_user_data = None
        remnawave_error = None
        
        if cached_data and isinstance(cached_data, dict):
            remnawave_user_data = cached_data.get('remnawave_user')
            remnawave_error = cached_data.get('remnawave_error')
            if remnawave_user_data:
                logger.info(f"⚡ RemnaWave данные из кеша: {remnawave_user_data.get('username')}")
            elif remnawave_error:
                logger.info(f"⚡ RemnaWave ошибка из кеша: {remnawave_error}")
        else:
            logger.info(f"🌊 Запрос данных RemnaWave для telegram_uid: {telegram_uid}")
            from backend.services.remnawave_service import remnawave_service
            
            try:
                remnawave_response = remnawave_service.get_user_by_telegram_id(telegram_uid)
                
                if remnawave_response:
                    if remnawave_response.get('error') == 'not_found':
                        logger.info(f"ℹ️ У юзера нет подписки RemnaWave")
                        remnawave_error = "no_remnawave_subscription"
                    elif remnawave_response.get('error') == 'unauthorized':
                        logger.error(f"❌ RemnaWave API: неверный токен")
                        remnawave_error = "api_unauthorized"
                    else:
                        remnawave_user_data = remnawave_response
                        logger.info(f"✅ RemnaWave данные получены: {remnawave_user_data.get('username')} (shortUuid: {remnawave_user_data.get('shortUuid')})")
                else:
                    logger.warning(f"⚠️ RemnaWave API не вернул данных")
                    remnawave_error = "api_no_response"
                    
            except Exception as remna_error:
                logger.error(f"❌ Ошибка запроса RemnaWave API: {remna_error}")
                remnawave_error = f"api_error: {str(remna_error)}"
            
            if not from_cache:
                try:
                    existing_cache = bot_cache.get(client_id, telegram_uid) or {}
                    if isinstance(existing_cache, dict):
                        if remnawave_user_data:
                            existing_cache['remnawave_user'] = remnawave_user_data
                        if remnawave_error:
                            existing_cache['remnawave_error'] = remnawave_error
                        bot_cache.set(client_id, telegram_uid, existing_cache)
                        logger.info("💾 RemnaWave данные сохранены в кеш")
                except Exception as cache_error:
                    logger.error(f"❌ Ошибка сохранения RemnaWave в кеш: {cache_error}")
        
        # Обрабатываем подписки через utils
        processed_subscriptions = process_subscriptions_list(subscriptions_data)
        processed_subscriptions = sort_subscriptions(processed_subscriptions, 'status')
        
        # Подсчет метрик
        active_count = sum(1 for s in processed_subscriptions if s['status'] == 'active')
        expiring_count = sum(1 for s in processed_subscriptions if s['status'] == 'expiring')
        expired_count = sum(1 for s in processed_subscriptions if s['status'] == 'expired')
        
        # Метрики производительности
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"📤 ОТПРАВЛЯЕМ USEDESK:")
        logger.info(f"   Клиент: {client_name}")
        logger.info(f"   Username: {telegram_username}")
        logger.info(f"   UID: {telegram_uid}")
        logger.info(f"   Подписок найдено: {len(processed_subscriptions)}")
        logger.info(f"   Подписки: {processed_subscriptions}")
        logger.info(f"⚡ Время обработки: {processing_time:.2f} секунд")
        
        # Подготовка данных для шаблона
        try:
            encoded_username = quote(telegram_username, safe='') if telegram_username else ''
            encoded_uid = quote(str(telegram_uid), safe='') if telegram_uid else ''
            encoded_total = quote(str(len(processed_subscriptions)), safe='')
        except Exception:
            encoded_username = telegram_username
            encoded_uid = str(telegram_uid)
            encoded_total = str(len(processed_subscriptions))

        # Абсолютный префикс домена нашего бекенда
        copy_base = request.host_url.rstrip('/')
        copy_path = f"/{SECURITY_HASH}_copy"
        manage_keys_path = f"/{SECURITY_HASH}_manage_keys"
        checklist_path = f"/{SECURITY_HASH}_checklist"

        response = render_template(
            'user_configs.html',
            client_id=client_id,
            client_name=client_name,
            telegram_username=telegram_username,
            telegram_uid=telegram_uid,
            subscriptions_data=processed_subscriptions,
            subscriptions_count=len(processed_subscriptions),
            error_msg=None,
            active_count=active_count,
            expiring_count=expiring_count,
            expired_count=expired_count,
            from_cache=from_cache,
            no_subscriptions_message=no_subscriptions_message,
            encoded_username=encoded_username,
            encoded_uid=encoded_uid,
            encoded_total=encoded_total,
            copy_base=copy_base,
            copy_path=copy_path,
            manage_keys_path=manage_keys_path,
            checklist_path=checklist_path,
            remnawave_user=remnawave_user_data,
            remnawave_error=remnawave_error
        )
        
        # UseDesk всегда ожидает JSON с HTML внутри!
        accept_header = request.headers.get('Accept', '')
        logger.info(f"📋 Accept заголовок: {accept_header}")
        logger.info("📤 ОТПРАВЛЯЕМ JSON С HTML ВИДЖЕТОМ ДЛЯ USEDESK")
        logger.info(f"   Размер HTML: {len(response)} символов")
        
        # Формируем JSON ответ с HTML внутри (как ожидает UseDesk)
        json_response = {
            "html": response,
            "subscriptions": processed_subscriptions,
            "client_name": client_name,
            "telegram_username": telegram_username,
            "telegram_uid": telegram_uid,
            "subscriptions_count": len(processed_subscriptions),
            "counts": {
                "total": len(processed_subscriptions),
                "active": active_count,
                "expiring": expiring_count,
                "expired": expired_count
            },
            "from_cache": from_cache
        }
        
        return jsonify(json_response)
        
    except Exception as e:
        logger.error(f"Ошибка в /useDeskGetUserConfigs: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@usedesk_bp.route('/api/subscriptions/<client_id>', methods=['GET', 'POST'])
def get_subscriptions_api(client_id):
    """JSON API для получения подписок клиента"""
    try:
        return jsonify({
            "status": "ok",
            "client_id": client_id,
            "message": "Используйте основной endpoint с client_id в параметрах"
        })
    except Exception as e:
        logger.error(f"Ошибка в /api/subscriptions: {e}")
        return jsonify({"error": str(e)}), 500


@usedesk_bp.route(f'/{SECURITY_HASH}_manage_keys', methods=['GET'])
def manage_keys():
    """Страница управления подписками клиента"""
    try:
        logger.info(f"🎯 ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_manage_keys")
        logger.info(f"🎯 Метод запроса: {request.method}")
        logger.info(f"🎯 URL: {request.url}")
        
        client_id = request.args.get('client_id')
        telegram_uid = request.args.get('telegram_uid')
        
        logger.info(f"🎯 Параметры: client_id={client_id}, telegram_uid={telegram_uid}")
        
        if not client_id or not telegram_uid:
            logger.error(f"❌ Отсутствуют обязательные параметры: client_id={client_id}, telegram_uid={telegram_uid}")
            return jsonify({"error": "Требуются параметры client_id и telegram_uid"}), 400
        
        # Получаем данные из кеша
        from backend.core.cache_manager import bot_cache
        cached_data = bot_cache.get(client_id, telegram_uid)
        
        if not cached_data:
            return jsonify({"error": "Данные не найдены в кеше"}), 404
        
        # Извлекаем данные из нового формата кеша
        subscriptions_list = []
        cached_client_name = "Клиент"
        
        if isinstance(cached_data, dict):
            # Новый формат кеша с дополнительными данными
            if cached_data.get('no_subscriptions'):
                logger.info("📭 У клиента нет подписок - возвращаем соответствующее сообщение")
                return jsonify({"error": "У клиента нет активных подписок"}), 404
                
            subscriptions_list = cached_data.get('subscriptions', [])
            cached_client_name = cached_data.get('client_name', 'Клиент')
            
        elif isinstance(cached_data, list):
            # Старый формат кеша - только список подписок
            subscriptions_list = cached_data
            
        else:
            logger.error(f"❌ Неожиданный тип данных кеша: {type(cached_data)} - {cached_data}")
            return jsonify({"error": "Некорректный формат данных в кеше"}), 500
        
        # Обрабатываем подписки
        processed_subscriptions = process_subscriptions_list(subscriptions_list)
        
        # Абсолютный префикс домена нашего бекенда (принудительно HTTPS)
        original_copy_base = request.host_url.rstrip('/')
        copy_base = original_copy_base
        if copy_base.startswith('http://'):
            copy_base = copy_base.replace('http://', 'https://')
            logger.info(f"🔄 Заменили HTTP на HTTPS: {original_copy_base} → {copy_base}")
        else:
            logger.info(f"✅ copy_base уже HTTPS: {copy_base}")
        
        manage_keys_path = f"/{SECURITY_HASH}_manage_keys"
        replace_key_path = f"/{SECURITY_HASH}_replace_key"
        delete_cache_path = f"/{SECURITY_HASH}_delete_client_cache"
        delete_device_path = f"/{SECURITY_HASH}_delete_device"
        
        logger.info(f"🔗 Полный URL delete_device: {copy_base}{delete_device_path}")

        # Добавляем отладочную информацию
        logger.info(f"🔍 Данные для manage_keys:")
        for i, sub in enumerate(processed_subscriptions):
            logger.info(f"   Подписка {i+1}: {sub.get('name')} - uuid: {sub.get('uuid')} - expires: {sub.get('expires')} - status: {sub.get('status', 'unknown')}")
        
        # Используем имя клиента из кеша или fallback
        client_name = cached_client_name if cached_client_name != "Клиент" else "Клиент"
        
        logger.info(f"🔍 Переменные шаблона:")
        logger.info(f"   copy_base: {copy_base}")
        logger.info(f"   replace_key_path: {replace_key_path}")
        logger.info(f"   client_name: {client_name}")
        logger.info(f"   Полный URL: {copy_base}{replace_key_path}")
        
        remnawave_user_data = None
        remnawave_devices = []
        remnawave_error = None
        
        if isinstance(cached_data, dict):
            remnawave_user_data = cached_data.get('remnawave_user')
            logger.info(f"🔍 DEBUG manage_keys: cached_data type = {type(cached_data)}")
            logger.info(f"🔍 DEBUG manage_keys: remnawave_user_data = {remnawave_user_data}")
            
            if remnawave_user_data and remnawave_user_data.get('uuid'):
                user_uuid = remnawave_user_data.get('uuid')
                logger.info(f"🌊 Запрос HWID устройств для uuid: {user_uuid}")
                logger.info(f"🔍 DEBUG: uuid = {user_uuid}, type = {type(user_uuid)}")
                
                from backend.services.remnawave_service import remnawave_service
                
                try:
                    logger.info(f"🔍 DEBUG: Вызываем get_hwid_devices с uuid={user_uuid}")
                    devices_response = remnawave_service.get_hwid_devices(user_uuid)
                    logger.info(f"🔍 DEBUG: devices_response = {devices_response}")
                    logger.info(f"🔍 DEBUG: devices_response type = {type(devices_response)}")
                    
                    if devices_response:
                        if devices_response.get('error') == 'unauthorized':
                            logger.error(f"❌ RemnaWave API: неверный токен")
                            remnawave_error = "api_unauthorized"
                        else:
                            remnawave_devices = devices_response.get('devices', [])
                            logger.info(f"✅ Получено {len(remnawave_devices)} HWID устройств")
                            logger.info(f"🔍 DEBUG: remnawave_devices = {remnawave_devices}")
                    else:
                        logger.warning(f"⚠️ RemnaWave API не вернул данных об устройствах")
                        remnawave_error = "api_no_response"
                        
                except Exception as remna_error:
                    logger.error(f"❌ Ошибка запроса HWID устройств: {remna_error}")
                    remnawave_error = f"api_error: {str(remna_error)}"
            else:
                remnawave_error = cached_data.get('remnawave_error', 'no_remnawave_user')
                logger.info(f"ℹ️ RemnaWave пользователь не найден в кеше")
        
        response = render_template(
            'manage_keys.html',
            client_id=client_id,
            client_name=client_name,
            telegram_username=f"ID: {telegram_uid}",
            telegram_uid=telegram_uid,
            subscriptions_data=processed_subscriptions,
            subscriptions_count=len(processed_subscriptions),
            copy_base=copy_base,
            manage_keys_path=manage_keys_path,
            replace_key_path=replace_key_path,
            delete_cache_path=delete_cache_path,
            remnawave_user=remnawave_user_data,
            remnawave_devices=remnawave_devices,
            remnawave_error=remnawave_error,
            delete_device_path=delete_device_path
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в manage_keys: {e}")
        return jsonify({"error": str(e)}), 500


@usedesk_bp.route(f'/{SECURITY_HASH}_replace_key', methods=['GET', 'POST'])
def replace_key():
    """Эндпоинт для замены ключа подписки"""
    try:
        logger.info(f"🎯 ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_replace_key")
        logger.info(f"🎯 Метод запроса: {request.method}")
        logger.info(f"🎯 URL: {request.url}")
        
        if request.method == 'GET':
            return jsonify({
                "message": "Эндпоинт замены ключа работает!",
                "method": "GET",
                "note": "Используйте POST для замены ключа"
            })
        
        data = request.get_json()
        client_id = data.get('client_id')
        telegram_uid = data.get('telegram_uid')
        uuid = data.get('uuid')
        
        logger.info(f"🎯 POST данные: client_id={client_id}, telegram_uid={telegram_uid}, uuid={uuid}")
        
        if not all([client_id, telegram_uid, uuid]):
            return jsonify({"success": False, "error": "Требуются параметры client_id, telegram_uid и uuid"}), 400
        
        from backend.core.cache_manager import bot_cache
        cached_data = bot_cache.get(client_id, telegram_uid)
        
        if cached_data:
            subscriptions_list = cached_data.get('subscriptions', []) if isinstance(cached_data, dict) else (cached_data if isinstance(cached_data, list) else [])
            
            target_subscription = None
            for sub in subscriptions_list:
                if sub.get('uuid') == uuid:
                    target_subscription = sub
                    break
            
            if target_subscription:
                subscription_name = target_subscription.get('name', '')
                if is_router_subscription(subscription_name):
                    logger.warning(f"❌ Попытка замены ключа роутерной подписки: {subscription_name}")
                    return jsonify({
                        "success": False, 
                        "error": f"Замена ключей роутерных подписок запрещена. Подписка '{subscription_name}' является роутерной."
                    }), 400
                
                logger.info(f"✅ Подписка '{subscription_name}' не является роутерной, замена ключа разрешена")
            else:
                logger.warning(f"⚠️ Подписка с UUID {uuid} не найдена в кеше")
        
        logger.info(f"🔄 Замена ключа для client_id: {client_id}, telegram_uid: {telegram_uid}, uuid: {uuid}")
        
        bot_response = send_replace_key_command(telegram_uid, uuid)
        
        if not bot_response or bot_response.startswith("❌"):
            logger.error(f"❌ Ошибка замены ключа: {bot_response}")
            return jsonify({"success": False, "error": "Не удалось заменить ключ"}), 500
        
        new_quickinstall = parse_replace_response(bot_response)
        
        if not new_quickinstall:
            logger.error(f"❌ Не удалось извлечь новый quickinstall из ответа: {bot_response[:200]}")
            return jsonify({"success": False, "error": "Не удалось получить новый ключ"}), 500
        
        try:
            cache_file_path = bot_cache._get_cache_file_path(client_id, telegram_uid)
            if cache_file_path.exists():
                cache_file_path.unlink()
                logger.info(f"🗑️ Удален файл кеша: {cache_file_path.name}")
            else:
                logger.info(f"🔍 Файл кеша не найден для удаления: {cache_file_path.name}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось очистить кеш: {e}")
        
        if new_quickinstall == "SUCCESS_BUT_NO_URL":
            logger.info(f"✅ Ключ успешно заменен (без прямого URL, требуется обновить подписки)")
            return jsonify({
                "success": True,
                "new_quickinstall": None,
                "message": "Ключ успешно заменен! Обновите страницу чтобы увидеть новый ключ.",
                "should_refresh": True
            })
        
        logger.info(f"✅ Ключ успешно заменен, новый quickinstall: {new_quickinstall}")
        
        return jsonify({
            "success": True,
            "new_quickinstall": new_quickinstall,
            "message": "Ключ успешно заменен"
        })
        
    except Exception as e:
        logger.error(f"Ошибка в replace_key: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@usedesk_bp.route(f'/{SECURITY_HASH}_delete_device', methods=['POST'])
def delete_device():
    try:
        logger.info(f"🎯 ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_delete_device")
        logger.info(f"🎯 Метод запроса: {request.method}")
        
        data = request.get_json()
        user_uuid = data.get('user_uuid')
        hwid = data.get('hwid')
        
        logger.info(f"🎯 POST данные: user_uuid={user_uuid}, hwid={hwid}")
        
        if not user_uuid or not hwid:
            logger.error(f"❌ Отсутствуют обязательные параметры: user_uuid={user_uuid}, hwid={hwid}")
            return jsonify({"success": False, "error": "Требуются параметры user_uuid и hwid"}), 400
        
        logger.info(f"🗑️ Удаление устройства: user_uuid={user_uuid}, hwid={hwid}")
        
        from backend.services.remnawave_service import remnawave_service
        
        success = remnawave_service.delete_hwid_device(user_uuid, hwid)
        
        if success:
            logger.info(f"✅ Устройство {hwid} успешно удалено")
            return jsonify({
                "success": True,
                "message": "Устройство успешно удалено"
            })
        else:
            logger.error(f"❌ Не удалось удалить устройство {hwid}")
            return jsonify({
                "success": False,
                "error": "Не удалось удалить устройство"
            }), 500
        
    except Exception as e:
        logger.error(f"❌ Ошибка в delete_device: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@usedesk_bp.route(f'/{SECURITY_HASH}_copy')
def copy_redirect():
    """Редирект для копирования текста в буфер обмена"""
    try:
        text = request.args.get('text', '')
        
        # Возвращаем простую HTML страницу с автокопированием
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Копирование</title>
            <script>
                function copyToClipboard() {{
                    const text = "{text}";
                    navigator.clipboard.writeText(text).then(function() {{
                        window.close();
                    }}, function() {{
                        // Fallback
                        const textArea = document.createElement('textarea');
                        textArea.value = text;
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                        setTimeout(function(){{ window.close(); }}, 350);
                    }});
                }}
                window.onload = copyToClipboard;
            </script>
        </head>
        <body>
            <p>Копирование...</p>
        </body>
        </html>
        """
        return html
        
    except Exception as e:
        logger.error(f"Ошибка в copy_redirect: {e}")
        return jsonify({"error": str(e)}), 500

