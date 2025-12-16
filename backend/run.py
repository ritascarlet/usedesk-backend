#!/usr/bin/env python3
"""
Скрипт запуска UseDesk Backend приложения
Поддерживает как обычный запуск, так и работу в качестве бинарного файла
"""

import os
import sys
import signal
from backend.app import app
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    bundle_dir = os.path.dirname(os.path.abspath(sys.executable))
    env_path = os.path.join(bundle_dir, '.env')
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    bundle_dir = os.path.dirname(current_dir)
    env_path = os.path.join(bundle_dir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    print(f"\n🛑 Получен сигнал {signum}, завершаем работу...")
    sys.exit(0)

def startup():
    """Инициализация приложения"""
    print("🚀 Запуск UseDesk Backend...")
    print(f"🔧 Версия 2.1")
    
    if getattr(sys, 'frozen', False):
        print("📦 Режим: Бинарный файл (PyInstaller)")
        print(f"📁 Рабочая директория: {bundle_dir}")
    else:
        print("🐍 Режим: Python скрипт")
    
    if os.path.exists(env_path):
        print(f"✅ Конфигурация загружена из: {env_path}")
    else:
        print(f"⚠️  Файл .env не найден в: {env_path}")
        print("Будут использованы переменные окружения системы")
    
    required_vars = [
        'TELEGRAM_API_ID',
        'TELEGRAM_API_HASH', 
        'TELEGRAM_PHONE',
        'USEDESK_API_TOKEN'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Не указаны обязательные переменные окружения: {', '.join(missing_vars)}")
        print("Создайте файл .env на основе .env.example")
        print(f"Путь к .env файлу: {env_path}")
        sys.exit(1)
    
    session_file = os.path.join(bundle_dir, 'admin_session.session')
    if os.path.exists(session_file):
        print(f"✅ Telegram сессия найдена: {session_file}")
    else:
        print(f"⚠️  Telegram сессия не найдена: {session_file}")
        print("🔐 Требуется первоначальная авторизация в Telegram")
        
        if setup_telegram_auth():
            print("✅ Авторизация Telegram завершена успешно!")
        else:
            print("❌ Ошибка авторизации Telegram. Проверьте настройки.")
            sys.exit(1)
    
    print("✅ UseDesk Backend готов к работе!")
    print("🌐 Доступные эндпоинты:")
    print("   - /aljsdhfaljsdhflahsjdflaksjhdflasjlkfjaslkdfjalsdjflaksjdflkasjflkajsdklfjal_useDeskGetUserConfigs?client_id=<number>")
    print("   - /api/subscriptions/<client_id> (JSON API)")
    print("   - /health")
    print("📱 Telegram операции выполняются через subprocess")
    print("🔒 Используется 64-битный HASH для безопасности")
    print("🖥️  Сервер запущен на http://0.0.0.0:5000")
    print("🔄 Для остановки нажмите Ctrl+C")
    
    print("🌐 Зарегистрированные маршруты Flask:")
    for rule in app.url_map.iter_rules():
        print(f"   {rule.rule} [{', '.join(rule.methods)}]")

def setup_telegram_auth():
    """Запуск интерактивной авторизации Telegram"""
    import asyncio
    
    try:
        print("\n🔐 === АВТОРИЗАЦИЯ TELEGRAM ===")
        print("📱 Сейчас будет отправлен SMS с кодом подтверждения")
        print("⏳ Подготовьтесь ввести код...")
        
        # Импортируем функции из telegram_sender
        from backend.services.telegram_sender import setup_telegram_session
        
        # Запускаем асинхронную авторизацию
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(setup_telegram_session())
        loop.close()
        
        print("🔐 === АВТОРИЗАЦИЯ ЗАВЕРШЕНА ===\n")
        return success
        
    except Exception as e:
        print(f"❌ Ошибка настройки Telegram авторизации: {e}")
        return False

if __name__ == '__main__':
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Запускаем инициализацию
        startup()
        
        # Запускаем планировщик очистки кеша
        try:
            from backend.app import cache_scheduler
            cache_scheduler.start()
        except Exception as scheduler_error:
            print(f"⚠️ Ошибка запуска планировщика очистки кеша: {scheduler_error}")
            print("🔄 Приложение продолжает работу без планировщика")
        
        try:
            # Запускаем Flask приложение
            app.run(host='0.0.0.0', port=5000, debug=False)
        finally:
            # Останавливаем планировщик при завершении
            try:
                cache_scheduler.stop()
            except:
                pass  # Игнорируем ошибки при завершении
    except KeyboardInterrupt:
        print("\n🛑 Получен Ctrl+C, завершаем работу...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)