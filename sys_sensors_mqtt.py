#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psutil
import time
import datetime as dt
import paho.mqtt.client as mqtt
import pytz
import json
from threading import Timer


class MainProcess(object):

    def __init__(self, logger_obj, settings_dict):
        self.settings = settings_dict
        self.logger = logger_obj
        self.disks = []
        self.mqtt_client = None
        self.is_run = False
        self.publish_timer = Timer(self.settings['update_interval'], self.mqtt_publish_timer)

    def utc_from_timestamp(self, timestamp: float) -> dt.datetime:
        """Return a UTC time from a timestamp."""
        return pytz.utc.localize(dt.datetime.utcfromtimestamp(timestamp))

    def as_local(self, dattim: dt.datetime) -> dt.datetime:
        """Convert a UTC datetime object to local time zone."""
        if dattim.tzinfo == self.settings['timezone']:
            return dattim
        if dattim.tzinfo is None:
            dattim = pytz.utc.localize(dattim)
        return dattim.astimezone(self.settings['timezone'])

    def get_last_boot(self):
        self.logger.debug('Get last boot')
        return str(self.as_local(self.utc_from_timestamp(psutil.boot_time())).isoformat())

    def mqtt_update_sensors(self):
        payload = {"memory_use": self.get_memory_usage(),
                   "last_boot": self.get_last_boot(),
                   }
        payload.update(self.get_disk_usage())
        payload.update({"soc_temperature": self.get_temp()})
        self.mqtt_client.publish(topic='system-sensors/sensor/{}/state'.format(self.settings['device_name']),
                                 payload=json.dumps(payload), qos=1, retain=False)

    def get_temp(self):
        self.logger.debug('Get SOC temperature')
        temp = '-'
        temps = psutil.sensors_temperatures()
        if 'soc_thermal' in temps.keys():
            temp = str(temps['soc_thermal'][0].current)
        return temp

    def get_disk_usage(self):
        self.logger.debug('Get disks usage')
        disks_payload = {}
        for disk in psutil.disk_partitions():
            if disk.mountpoint in self.disks:
                disks_payload.update({
                    'disk_use_{}'.format(disk.mountpoint).replace('/', '_'): str(psutil.disk_usage(disk.mountpoint).percent)
                })
        return disks_payload

    def get_memory_usage(self):
        self.logger.debug('Get memory usage')
        return str(psutil.virtual_memory().percent)

    def mqtt_send_config(self):
        retain = False
        # SOC temperature.
        payload = {'name': '{}_soc_temperature'.format(self.settings['device_name']),
                   'state_topic': 'system-sensors/sensor/{}/state'.format(self.settings['device_name']),
                   'device_class': 'temperature',
                   'unit_of_measurement': '°C',
                   'value_template': '{{ value_json.soc_temperature }}',
                   'unique_id': '{}_sensor_soc_temperature'.format(self.settings['device_name'].lower()),
                   'device': {
                     'identifiers': ['{}_sensor'.format(self.settings['device_name'].lower())],
                     'name': '{}_sensors'.format(self.settings['device_name'].lower()),
                     'model': self.settings['model'],
                     'manufacturer': self.settings['manufacturer']
                 }
                   }
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/soc_temperature/config'.format(self.settings['device_name']),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        # Disks use.
        self.disks = []
        for disk in psutil.disk_partitions():
            self.disks.append(disk.mountpoint)
        for disk in self.disks:
            disk = disk.replace('/', '_')
            payload = {'name': '{}_disk_use_{}'.format(self.settings['device_name'], disk),
                       'state_topic': 'system-sensors/sensor/{}/state'.format(self.settings['device_name']),
                       'unit_of_measurement': '%',
                       'icon': 'mdi:harddisk',
                       'value_template': '{{{{ value_json.disk_use_{} }}}}'.format(disk),
                       'unique_id': '{0}_sensor_disk_use_{1}'.format(self.settings['device_name'].lower(), disk),
                       'device': {
                           'identifiers': ['{}_sensor'.format(self.settings['device_name'].lower())],
                           'name': '{}_sensors'.format(self.settings['device_name'].lower()),
                           'model': self.settings['model'],
                           'manufacturer': self.settings['manufacturer']
                       }
                       }
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/disk_use_{1}/config'.format(self.settings['device_name'], disk),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
        # Memory use.
        payload = {'name': '{}_memory_use'.format(self.settings['device_name']),
                   'state_topic': 'system-sensors/sensor/{}/state'.format(self.settings['device_name']),
                   'unit_of_measurement': '%',
                   'icon': 'mdi:memory',
                   'value_template': '{{ value_json.memory_use }}',
                   'unique_id': '{}_sensor_memory_use'.format(self.settings['device_name'].lower()),
                   'device': {
                       'identifiers': ['{}_sensor'.format(self.settings['device_name'].lower())],
                       'name': '{}_sensors'.format(self.settings['device_name'].lower()),
                       'model': self.settings['model'],
                       'manufacturer': self.settings['manufacturer']
                   }
                   }
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/memory_use/config'.format(self.settings['device_name']),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        # Last boot.
        payload = {'device_class': 'timestamp',
                   'name': '{}_last_boot'.format(self.settings['device_name']),
                   'state_topic': 'system-sensors/sensor/{}/state'.format(self.settings['device_name']),
                   'icon': 'mdi:clock-start',
                   'value_template': '{{ value_json.last_boot }}',
                   'unique_id': '{}_sensor_last_boot'.format(self.settings['device_name'].lower()),
                   'device': {
                       'identifiers': ['{}_sensor'.format(self.settings['device_name'].lower())],
                       'name': '{}_sensors'.format(self.settings['device_name'].lower()),
                       'model': self.settings['model'],
                       'manufacturer': self.settings['manufacturer']
                   }
                   }
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/last_boot/config'.format(self.settings['device_name']),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )

    def mqtt_connect(self):
        con_ok = False
        while not con_ok and self.is_run:
            try:
                self.mqtt_client.connect(self.settings['mqtt']['hostname'], self.settings['mqtt']['port'])
                con_ok = True
            except:
                self.logger.debug('No connection to {}:{}'.format(self.settings['mqtt']['hostname'],
                                  self.settings['mqtt']['port']))
                self.logger.debug('Reconnect in 60 seconds')
                time.sleep(60)
                self.logger.debug('Reconnect to MQTT broker')

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.debug('Connection to MQTT broker successful')
            self.mqtt_send_config()
            self.logger.debug('Sent config to MQTT broker')
        elif rc == 1:
            self.logger.error('Connection to MQTT broker refused. Incorrect protocol version')
            self.stop()
        elif rc == 2:
            self.logger.error('Connection to MQTT broker refused. Invalid client identifier')
            self.stop()
        elif rc == 3:
            self.logger.debug('Connection to MQTT broker refused. Server unavailable')
        elif rc == 4:
            self.logger.error('Connection to MQTT broker refused. Bad username or password')
            self.stop()
        elif rc == 5:
            self.logger.error('Connection to MQTT broker refused. Not authorised')
            self.stop()

    def on_disconnect(self, client, userdata, rc):
        self.logger.debug('Disconnected from MQTT broker. {}'.format(rc))

    def mqtt_publish_timer(self):
        self.mqtt_update_sensors()
        self.logger.debug('Updated sensors states to MQTT broker')
        self.logger.debug('Next update in {} seconds'.format(self.settings['update_interval']))
        self.publish_timer = Timer(self.settings['update_interval'], self.mqtt_publish_timer)
        self.publish_timer.start()

    def run(self):
        self.mqtt_client = mqtt.Client(client_id=self.settings['client_id'])
        self.mqtt_client.username_pw_set(self.settings['mqtt']['user'], self.settings['mqtt']['password'])
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.logger.info('Connecting to MQTT broker on host {}:{}'.format(self.settings['mqtt']['hostname'],
                                                                          self.settings['mqtt']['port']))
        self.is_run = True
        self.mqtt_connect()
        self.logger.info('Connected to MQTT broker on host {}:{}'.format(self.settings['mqtt']['hostname'],
                                                                         self.settings['mqtt']['port']))
        self.mqtt_client.loop_start()
        self.publish_timer = Timer(self.settings['update_interval'], self.mqtt_publish_timer)
        self.publish_timer.start()
        while self.is_run:
            time.sleep(1)

    def stop(self):
        self.logger.info('Stopping')
        self.is_run = False
        self.publish_timer.cancel()
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
