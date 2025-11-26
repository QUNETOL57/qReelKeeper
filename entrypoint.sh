#!/bin/bash
set -e

# Генерация конфигурации WireGuard из base64-encoded переменной
if [ -n "$WG_CONFIG_BASE64" ]; then
    echo "Создание конфигурации WireGuard из WG_CONFIG_BASE64..."
    
    mkdir -p /config/wg_confs
    
    # Декодируем base64 конфиг и сохраняем
    echo "$WG_CONFIG_BASE64" | base64 -d > /config/wg_confs/wg0.conf
    
    echo "Конфигурация WireGuard создана успешно"
    chmod 600 /config/wg_confs/wg0.conf
else
    echo "ПРЕДУПРЕЖДЕНИЕ: WG_CONFIG_BASE64 не установлен. Контейнер запущен без VPN."
fi

# Запуск команды, переданной в CMD
exec "$@"

