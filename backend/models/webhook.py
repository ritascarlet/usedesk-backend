"""
Pydantic модели для валидации UseDesk webhook данных
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class MessengerInfo(BaseModel):
    """Информация о мессенджере клиента"""
    type: str = Field(..., description="Тип мессенджера (telegram, whatsapp и т.д.)")
    id: str = Field(..., description="ID или username в мессенджере")
    
    class Config:
        extra = "allow"  # Разрешаем дополнительные поля


class ClientData(BaseModel):
    """Данные клиента из UseDesk"""
    name: Optional[str] = Field(None, description="Имя клиента")
    emails: List[str] = Field(default_factory=list, description="Email адреса")
    phones: List[str] = Field(default_factory=list, description="Телефоны")
    messengers: List[MessengerInfo] = Field(default_factory=list, description="Мессенджеры")
    social_services: List[Dict] = Field(default_factory=list, description="Социальные сети")
    addresses: List[str] = Field(default_factory=list, description="Адреса")
    sites: List[str] = Field(default_factory=list, description="Сайты")
    
    class Config:
        extra = "allow"


class ChannelData(BaseModel):
    """Данные канала связи"""
    type: str = Field(..., description="Тип канала (telegram, email и т.д.)")
    data: Optional[str] = Field(None, description="Данные канала (username, email и т.д.)")
    id: Optional[int] = Field(None, description="ID канала в UseDesk")
    
    class Config:
        extra = "allow"


class UseDeskWebhook(BaseModel):
    """
    Модель для валидации UseDesk webhook.
    Описывает структуру данных которые приходят от UseDesk.
    """
    ticket_id: int = Field(..., description="ID тикета в UseDesk")
    subject: str = Field(..., description="Тема тикета")
    client_id: int | str = Field(..., description="ID клиента в UseDesk")
    channel_type: str = Field(..., description="Тип канала связи")
    channel_id: int = Field(..., description="ID канала")
    contact: str | int = Field(..., description="Контактные данные (обычно Telegram UID)")
    client_data: ClientData = Field(..., description="Данные клиента")
    channel_data: ChannelData = Field(..., description="Данные канала")
    is_auto_load: str = Field(default="0", description="Флаг автозагрузки")
    timeout: int = Field(default=25, description="Таймаут для ответа")
    
    @field_validator('client_id')
    @classmethod
    def validate_client_id(cls, v):
        """Валидация client_id - не должен быть шаблоном"""
        if isinstance(v, str) and v == '{{client_id}}':
            raise ValueError('client_id не может быть шаблоном {{client_id}}')
        return v
    
    @field_validator('channel_type')
    @classmethod
    def validate_channel_type(cls, v):
        """Валидация типа канала - поддерживаем только telegram"""
        if v != 'telegram':
            raise ValueError(f'Неподдерживаемый тип канала: {v}. Поддерживается только telegram.')
        return v
    
    class Config:
        extra = "allow"  # Разрешаем дополнительные поля от UseDesk
        
    def get_telegram_uid(self) -> Optional[str]:
        """
        Извлекает Telegram UID из webhook данных.
        Использует утилиты из webhook_parsers.
        """
        from backend.utils.webhook_parsers import extract_telegram_uid_from_webhook
        return extract_telegram_uid_from_webhook(self.model_dump())
    
    def get_telegram_username(self) -> str:
        """Извлекает Telegram username для отображения"""
        from backend.utils.webhook_parsers import extract_telegram_username_from_webhook
        return extract_telegram_username_from_webhook(self.model_dump())
    
    def get_client_name(self) -> str:
        """Извлекает имя клиента"""
        from backend.utils.webhook_parsers import extract_client_name_from_webhook
        return extract_client_name_from_webhook(self.model_dump())

