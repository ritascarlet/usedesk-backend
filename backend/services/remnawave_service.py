import http.client
import json
import logging
import requests
from typing import Optional, Dict, Any, List
from urllib.parse import quote

from backend.config.settings import REMNA_API_DOMAIN, REMNA_API_TOKEN

logger = logging.getLogger(__name__)


class RemnaWaveService:
    
    def __init__(self):
        self.domain = REMNA_API_DOMAIN
        self.token = REMNA_API_TOKEN
        
        if not self.token:
            logger.warning("⚠️ REMNA_API_TOKEN не установлен")
    
    def _make_request(self, method: str, endpoint: str, payload: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            conn = http.client.HTTPSConnection(self.domain)
            
            headers = {
                'Authorization': f"Bearer {self.token}"
            }
            
            if payload:
                headers['Content-Type'] = "application/json"
            
            logger.info(f"📤 RemnaWave API: {method} {endpoint}")
            logger.debug(f"🔑 Токен (первые 20 символов): {self.token[:20] if self.token else 'НЕТ'}")
            logger.debug(f"🌐 Домен: {self.domain}")
            
            conn.request(method, endpoint, payload, headers)
            res = conn.getresponse()
            data = res.read()
            
            response_text = data.decode("utf-8")
            logger.info(f"📥 RemnaWave HTTP статус: {res.status}")
            logger.debug(f"📥 RemnaWave ответ: {response_text[:500]}")
            
            try:
                response_data = json.loads(response_text)
                logger.debug(f"📋 Распарсенный JSON: {response_data}")
            except json.JSONDecodeError:
                logger.error(f"❌ Не удалось распарсить JSON: {response_text}")
                return None
            
            if res.status == 401:
                logger.error(f"❌ RemnaWave API: неверный токен (401)")
                return {"error": "unauthorized", "message": "Unauthorized", "statusCode": 401}
            
            if res.status == 404:
                logger.warning(f"⚠️ RemnaWave API: не найдено (404)")
                return response_data
            
            if res.status != 200:
                logger.warning(f"⚠️ RemnaWave API вернул статус {res.status}")
                logger.warning(f"⚠️ Ответ: {response_text[:200]}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка запроса к RemnaWave API: {e}")
            return None
        finally:
            try:
                conn.close()
            except:
                pass
    
    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        if not self.token:
            logger.warning("⚠️ RemnaWave API токен не установлен, пропускаем запрос")
            return None
        
        telegram_id_encoded = quote(str(telegram_id), safe='')
        endpoint = f"/api/users/by-telegram-id/{telegram_id_encoded}"
        
        response = self._make_request("GET", endpoint)
        
        if not response:
            return None
        
        if "errorCode" in response and response.get("errorCode") == "A062":
            logger.info(f"ℹ️ У юзера {telegram_id} нет подписки RemnaWave")
            return {"error": "not_found", "message": "Users not found"}
        
        if "message" in response and response.get("statusCode") == 401:
            logger.error("❌ RemnaWave API: Unauthorized")
            return {"error": "unauthorized", "message": "Unauthorized"}
        
        if "response" in response and isinstance(response["response"], list) and len(response["response"]) > 0:
            user_data = response["response"][0]
            logger.info(f"✅ Найден RemnaWave пользователь: {user_data.get('username')} (shortUuid: {user_data.get('shortUuid')})")
            return user_data
        
        logger.warning(f"⚠️ Неожиданный формат ответа от RemnaWave API")
        return None
    
    def get_hwid_devices(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        if not self.token:
            logger.warning("⚠️ RemnaWave API токен не установлен, пропускаем запрос")
            return None
        
        user_uuid_encoded = quote(str(user_uuid), safe='')
        endpoint = f"/api/hwid/devices/{user_uuid_encoded}"
        
        response = self._make_request("GET", endpoint)
        
        if not response:
            return None
        
        if "message" in response and response.get("statusCode") == 401:
            logger.error("❌ RemnaWave API: Unauthorized")
            return {"error": "unauthorized", "message": "Unauthorized"}
        
        if "response" in response and "devices" in response["response"]:
            devices = response["response"]["devices"]
            total = response["response"].get("total", len(devices))
            logger.info(f"✅ Найдено {total} HWID устройств для пользователя {user_uuid}")
            return response["response"]
        
        logger.warning(f"⚠️ Неожиданный формат ответа от RemnaWave API")
        return None
    
    def delete_hwid_device(self, user_uuid: str, hwid: str) -> bool:
        if not self.token:
            logger.warning("⚠️ RemnaWave API токен не установлен, пропускаем запрос")
            return False
        
        url = f"https://{self.domain}/api/hwid/devices/delete"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        payload = {
            "userUuid": user_uuid,
            "hwid": hwid
        }
        
        logger.info(f"🗑️ Удаление HWID устройства: {hwid} для пользователя {user_uuid}")
        logger.debug(f"📤 POST {url}")
        logger.debug(f"📋 Payload: {payload}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            logger.info(f"📥 Статус ответа: {response.status_code}")
            logger.debug(f"📥 Ответ: {response.text[:500]}")
            
            if response.status_code == 401:
                logger.error("❌ RemnaWave API: Unauthorized")
                return False
            
            if response.status_code == 200:
                logger.info(f"✅ HWID устройство {hwid} успешно удалено")
                return True
            else:
                logger.warning(f"⚠️ Неожиданный статус: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка при удалении HWID устройства: {e}")
            return False
    
    def get_platform_emoji(self, platform: str) -> str:
        platform_lower = platform.lower() if platform else ""
        
        emoji_map = {
            'android': '📱',
            'ios': '📱',
            'iphone': '📱',
            'windows': '💻',
            'macos': '💻',
            'mac': '💻',
            'linux': '🐧',
            'router': '🔧'
        }
        
        for key, emoji in emoji_map.items():
            if key in platform_lower:
                return emoji
        
        return '📟'
    
    def get_user_agent_emoji(self, user_agent: str) -> str:
        user_agent_lower = user_agent.lower() if user_agent else ""
        
        emoji_map = {
            'android': '📱',
            'ios': '📱',
            'iphone': '📱',
            'windows': '💻',
            'macos': '💻',
            'mac': '💻',
            'linux': '🐧'
        }
        
        for key, emoji in emoji_map.items():
            if key in user_agent_lower:
                return emoji
        
        return '🖥️'


remnawave_service = RemnaWaveService()

