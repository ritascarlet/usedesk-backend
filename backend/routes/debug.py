import logging
from flask import Blueprint, request, jsonify

from backend.config.settings import SECURITY_HASH
from backend.services.remnawave_service import remnawave_service

logger = logging.getLogger(__name__)

debug_bp = Blueprint('debug', __name__)


@debug_bp.route(f'/{SECURITY_HASH}_debug_remna', methods=['GET', 'POST'])
def debug_remna():
    try:
        logger.info(f"🔍 DEBUG: RemnaWave API тестирование")
        
        if request.method == 'GET':
            telegram_id = request.args.get('telegram_id')
            user_uuid = request.args.get('user_uuid')
            action = request.args.get('action', 'get_user')
        else:
            data = request.get_json()
            telegram_id = data.get('telegram_id')
            user_uuid = data.get('user_uuid')
            action = data.get('action', 'get_user')
        
        result = {
            "action": action,
            "params": {
                "telegram_id": telegram_id,
                "user_uuid": user_uuid
            },
            "api_config": {
                "domain": remnawave_service.domain,
                "token_set": bool(remnawave_service.token),
                "token_length": len(remnawave_service.token) if remnawave_service.token else 0
            }
        }
        
        if action == 'get_user' and telegram_id:
            logger.info(f"🔍 Тест 1: Получение пользователя по telegram_id={telegram_id}")
            user_response = remnawave_service.get_user_by_telegram_id(telegram_id)
            result['user_response'] = user_response
            
            if user_response and not user_response.get('error'):
                result['user_found'] = True
                result['uuid'] = user_response.get('uuid')
                result['shortUuid'] = user_response.get('shortUuid')
                result['username'] = user_response.get('username')
                result['subLastUserAgent'] = user_response.get('subLastUserAgent')
            else:
                result['user_found'] = False
                result['error'] = user_response
        
        if action == 'get_devices' and user_uuid:
            logger.info(f"🔍 Тест 2: Получение устройств для user_uuid={user_uuid}")
            devices_response = remnawave_service.get_hwid_devices(user_uuid)
            result['devices_response'] = devices_response
            
            if devices_response and not devices_response.get('error'):
                result['devices_found'] = True
                result['devices_count'] = devices_response.get('total', 0)
                result['devices'] = devices_response.get('devices', [])
            else:
                result['devices_found'] = False
                result['error'] = devices_response
        
        if action == 'full_test' and telegram_id:
            logger.info(f"🔍 Полный тест для telegram_id={telegram_id}")
            
            user_response = remnawave_service.get_user_by_telegram_id(telegram_id)
            result['step1_user_response'] = user_response
            
            if user_response and not user_response.get('error'):
                user_uuid = user_response.get('uuid')
                result['step1_success'] = True
                result['uuid'] = user_uuid
                result['shortUuid'] = user_response.get('shortUuid')
                
                if user_uuid:
                    logger.info(f"🔍 Запрашиваем устройства для uuid={user_uuid}")
                    devices_response = remnawave_service.get_hwid_devices(user_uuid)
                    result['step2_devices_response'] = devices_response
                    
                    if devices_response and not devices_response.get('error'):
                        result['step2_success'] = True
                        result['devices_count'] = devices_response.get('total', 0)
                        result['devices'] = devices_response.get('devices', [])
                    else:
                        result['step2_success'] = False
                        result['step2_error'] = devices_response
            else:
                result['step1_success'] = False
                result['step1_error'] = user_response
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в debug_remna: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

