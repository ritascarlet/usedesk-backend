"""
Endpoints для работы с Outline чеклистом
"""
import logging
from flask import Blueprint, request, render_template, jsonify

from backend.config.settings import SECURITY_HASH
from backend.services.outline_service import outline_service

logger = logging.getLogger(__name__)

outline_bp = Blueprint('outline', __name__)


@outline_bp.route('/aljsdhfaljsdhflahsjdflaksjhdflasjlkfjaslkdfjalsdjflaksjdflkasjflkajsdklfjal_checklist_outline_fooowtfoooo', methods=['GET'])
def show_checklist_public():
    return show_checklist()


@outline_bp.route(f'/{SECURITY_HASH}_checklist', methods=['GET'])
def show_checklist():
    """Отображает страницу с чеклистом для агентов поддержки"""
    try:
        logger.info(f"🎯 ВЫЗВАН ЭНДПОИНТ: /{SECURITY_HASH}_checklist")
        logger.info(f"🎯 Метод запроса: {request.method}")
        logger.info(f"🎯 URL: {request.url}")
        
        # Получаем параметры (необязательные)
        client_id = request.args.get('client_id', '')
        telegram_uid = request.args.get('telegram_uid', '')
        client_name = request.args.get('client_name', 'Клиент')
        
        # Параметр для принудительного обновления
        refresh_value = request.args.get('refresh')
        force_refresh = str(refresh_value).lower() in ('1', 'true', 'yes') if refresh_value else False
        
        logger.info(f"📋 Параметры: client_id={client_id}, telegram_uid={telegram_uid}, client_name={client_name}")
        
        if force_refresh:
            logger.info("🔄 Запрошено принудительное обновление чеклиста")
        
        # Получаем коллекцию чеклистов через сервис
        collection_data = outline_service.get_checklist_collection(
            use_cache=not force_refresh,
            force_refresh=force_refresh
        )
        
        logger.info(f"📄 Получена коллекция: '{collection_data['title']}'")
        logger.info(f"   Источник: {'Outline' if collection_data['from_outline'] else 'Fallback'}")
        logger.info(f"   Из кеша: {collection_data.get('from_cache', False)}")
        logger.info(f"   Документов: {len(collection_data.get('documents', []))}")
        
        # Абсолютный префикс домена
        copy_base = request.host_url.rstrip('/')
        if copy_base.startswith('http://'):
            copy_base = copy_base.replace('http://', 'https://')
        
        # Пути для навигации
        manage_keys_path = f"/{SECURITY_HASH}_manage_keys"
        user_configs_path = f"/{SECURITY_HASH}_useDeskGetUserConfigs"
        checklist_path = f"/{SECURITY_HASH}_checklist"
        
        # Рендерим шаблон
        response = render_template(
            'checklist.html',
            checklist_title=collection_data['title'],
            documents=collection_data.get('documents', []),
            from_outline=collection_data['from_outline'],
            from_cache=collection_data.get('from_cache', False),
            last_updated=collection_data.get('last_updated', ''),
            error_message=collection_data.get('error'),
            client_id=client_id,
            telegram_uid=telegram_uid,
            client_name=client_name,
            copy_base=copy_base,
            manage_keys_path=manage_keys_path,
            user_configs_path=user_configs_path,
            checklist_path=checklist_path
        )
        
        logger.info(f"✅ Чеклист отрендерен успешно")
        return response
        
    except Exception as e:
        logger.error(f"❌ Ошибка в show_checklist: {e}", exc_info=True)
        return jsonify({"error": f"Ошибка отображения чеклиста: {str(e)}"}), 500


@outline_bp.route(f'/api/checklist/refresh', methods=['POST'])
def refresh_checklist():
    """API endpoint для принудительного обновления чеклиста"""
    try:
        logger.info("🔄 API: Запрос на обновление чеклиста")
        
        checklist_data = outline_service.get_checklist(
            use_cache=False,
            force_refresh=True
        )
        
        logger.info(f"✅ Чеклист обновлен: '{checklist_data['title']}'")
        
        return jsonify({
            "success": True,
            "message": "Чеклист успешно обновлен",
            "data": {
                "title": checklist_data['title'],
                "from_outline": checklist_data['from_outline'],
                "last_updated": checklist_data.get('last_updated', ''),
                "content_length": len(checklist_data['content'])
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления чеклиста: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@outline_bp.route(f'/api/checklist/status', methods=['GET'])
def checklist_status():
    """Проверяет статус интеграции с Outline"""
    try:
        from backend.config.outline import is_outline_enabled, validate_outline_config
        
        enabled = is_outline_enabled()
        is_valid, message = validate_outline_config()
        
        # Пробуем получить чеклист для проверки доступности
        test_result = None
        if enabled:
            checklist_data = outline_service.get_checklist(use_cache=True)
            test_result = {
                "success": checklist_data['from_outline'],
                "title": checklist_data['title'],
                "from_cache": checklist_data.get('from_cache', False)
            }
        
        return jsonify({
            "enabled": enabled,
            "valid": is_valid,
            "message": message,
            "test_result": test_result,
            "cache_size": len(outline_service._cache)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки статуса Outline: {e}")
        return jsonify({
            "enabled": False,
            "error": str(e)
        }), 500

