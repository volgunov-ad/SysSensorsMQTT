The MQTT client sends the following data to the MQTT broker with the specified frequency:
- SOC temperature;
- time of the last system startup;
- percentage of memory load;
- percent drive load.

When the client is turned on, if it does not detect the MQTT broker at the specified address,
the client continues to try connect every minute.

The client logs 2 logs in the /var/log path: sys_sensors_mqtt_info.log and sys_sensors_mqtt_error.log.

INSTALLATION
- Install pip:
    sudo apt-get install python3-pip
- Install additional packages:
    sudo apt-get install build-essential
    sudo pip3 install setuptools
    sudo pip3 install pyyaml
    sudo pip3 install psutil
    sudo pip3 install paho-mqtt
    sudo pip3 install pytz
- Transfer the service file to the UNIX system (just in case):
    sudo dos2unix sys_sensors_mqtt_daemon.py
- Make the service file executable:
    sudo chmod u + x sys_sensors_mqtt_daemon.py
- Enable service:
    sudo cp sys_sensors_mqtt.service/etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable sys_sensors_mqtt
    sudo systemctl start sys_sensors_mqtt
You can turn off the service with the command: sudo systemctl stop sys_sensors_mqtt
You can restart the service with the command: sudo systemctl restart sys_sensors_mqtt

Based on https://github.com/Sennevds/system_sensors

То же самое по русски.
Клиент MQTT отправляет следующе данные на MQTT брокер с заданной периодичностью:
- температура SOC;
- время последнего запуска системы;
- процент загрузки памяти;
- проценты загрузки дисков.

При включении клиента, если он не обнаруживает MQTT брокер по заданному адресу,
то клиент продолжает пытаться подключиться через каждую минуту.

Клиент ведет 2 журнала в пути /var/log: sys_sensors_mqtt_info.log и sys_sensors_mqtt_error.log.

УСТАНОВКА
- Установить pip:
    sudo apt-get install python3-pip
- Установить дополнительные пакеты:
    sudo apt-get install build-essential
    sudo pip3 install setuptools
    sudo pip3 install pyyaml
    sudo pip3 install psutil
    sudo pip3 install paho-mqtt
    sudo pip3 install pytz
- Перевести файл службы в систему UNIX (на всякий случай):
    sudo dos2unix sys_sensors_mqtt_daemon.py
- Сделать файл службы исполняемым:
    sudo chmod u+x sys_sensors_mqtt_daemon.py
- Включить службу:
    sudo cp sys_sensors_mqtt.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable sys_sensors_mqtt
    sudo systemctl start sys_sensors_mqtt
Выключить службу можно командой: sudo systemctl stop sys_sensors_mqtt
Перезапустить службу можно командой: sudo systemctl restart sys_sensors_mqtt

Сделано на основе https://github.com/Sennevds/system_sensors
