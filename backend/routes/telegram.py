"""
Endpoints для работы с Telegram
"""
import time
import logging
from flask import Blueprint, request, jsonify
from backend.services.telegram_service import send_message_to_bot

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)


@telegram_bp.route('/api/webhook', methods=['POST'])
def webhook_handler():
    """Обработчик вебхуков (универсальный)"""
    try:
        data = request.get_json()
        logger.info(f"Получен webhook: {data}")
        
        return jsonify({
            "success": True,
            "message": "Webhook обработан",
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }), 500


@telegram_bp.route('/api/telegram/send', methods=['POST'])
def send_telegram_message():
    """Отправляет сообщение в Telegram"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Требуется поле 'message'"}), 400
        
        message = data['message']
        logger.info(f"Отправка Telegram сообщения: {message}")
        
        response = send_message_to_bot(message)
        
        return jsonify({
            "success": True,
            "response": response,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки Telegram сообщения: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }), 500


@telegram_bp.route('/api/send_notification', methods=['POST'])
def send_notification():
    """Отправляет уведомление через внешний API (пример POST запроса)"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({"error": "Требуется поле 'message'"}), 400
        
        # Пример POST запроса к внешнему API
        notification_data = {
            "message": data['message'],
            "timestamp": time.time(),
            "source": "usedesk_backend"
        }
        
        # Примерный POST запрос (можно заменить на реальный API)
        logger.info(f"Отправка POST уведомления: {notification_data}")
        
        # Симуляция POST запроса
        return jsonify({
            "success": True,
            "message": "Уведомление отправлено",
            "data": notification_data
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

