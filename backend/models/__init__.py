"""
Models package - Pydantic модели для валидации данных
"""
from backend.models.webhook import UseDeskWebhook, ClientData, ChannelData, MessengerInfo

__all__ = [
    'UseDeskWebhook',
    'ClientData',
    'ChannelData',
    'MessengerInfo'
]

