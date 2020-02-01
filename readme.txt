Клиент MQTT отправляет следующе данные на MQTT брокер с заданной периодичностью:
- температура SOC;
- время последнего запуска системы;
- процент загрузки памяти;
- проценты загрузки дисков.

- Установить pip:
    sudo apt-get install python3-pip

    sudo apt-get install build-essential
    sudo pip3 install setuptools
    sudo pip3 install pyyaml
    sudo pip3 install psutil
    sudo pip3 install paho-mqtt
    sudo pip3 install pytz
- Перевести файл службы в систему UNIX (на всякий случай):
    sudo dos2unix sys_sensors_daemon.py
- Сделать файл службы исполняемым:
    sudo chmod u+x sys_sensors_daemon.py

    sudo cp sys_sensors_mqtt.service /etc/systemd/system
    sudo systemctl daemon-reload
    sudo systemctl enable sys_sensors_mqtt
    sudo systemctl start sys_sensors_mqtt