<h1>SysSensorsMQTT</h1>
<h3>DESCRIPTION</h3>

The MQTT client sends the following data to the MQTT broker with the specified frequency:

* SOC temperature;
* time of the last system startup;
* percentage of memory load;
* percent drive load.

![lovelace card](/images/image1.png)

When the client is turned on, if it does not detect the MQTT broker at the specified address,
the client continues to try connect every minute.

The client logs 2 logs in the /var/log path: sys_sensors_mqtt_info.log and sys_sensors_mqtt_error.log.

Tested only on Vero 4K.

<h3>INSTALLATION</h3>

* Install pip:
  * sudo apt-get install python3-pip
* Install additional packages:
  * sudo apt-get install gcc python3-dev (maybe build-essential)
  * sudo pip3 install setuptools
  * sudo pip3 install pyyaml
  * sudo pip3 install psutil
  * sudo pip3 install paho-mqtt
  * sudo pip3 install pytz

* Copy client files to the desired path, for example, /home/osmc/SysSensorsMQTT
* Go to the created path:
  * cd /home/osmc/SysSensorsMQTT
* Set the necessary settings in the settings.yaml file:
  * nano settings.yaml
* Edit the sys_sensors_mqtt.service file:
  * nano sys_sensors_mqtt.service
  * set in the line "WorkingDirectory=/home/osmc/SysSensorsMQTT" the correct path to the newly copied files
  * do the same in the line "ExecStart=/home/osmc/SysSensorsMQTT/sys_sensors_mqtt_daemon.py", leave /sys_sensors_mqtt_daemon.py
* Transfer the service file to the UNIX system (just in case):
  * sudo dos2unix sys_sensors_mqtt_daemon.py
* Make the service file executable:
  * sudo chmod u + x sys_sensors_mqtt_daemon.py
* Enable service:
  * sudo cp sys_sensors_mqtt.service/etc/systemd/system
  * sudo systemctl daemon-reload
  * sudo systemctl enable sys_sensors_mqtt
  * sudo systemctl start sys_sensors_mqtt

You can turn off the service with the command: sudo systemctl stop sys_sensors_mqtt

You can restart the service with the command: sudo systemctl restart sys_sensors_mqtt

Based on https://github.com/Sennevds/system_sensors
