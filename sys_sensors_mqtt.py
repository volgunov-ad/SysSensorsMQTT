#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import json
from os import system
from threading import Timer
import time

import paho.mqtt.client as mqtt
import psutil
import pytz


class MainProcess(object):

    def __init__(self, logger_obj, settings_dict):
        self.settings = settings_dict
        self.logger = logger_obj
        self.disks = []
        self.mqtt_client = None
        self.is_run = False
        self.publish_timer = Timer(self.settings['update_interval'], self.mqtt_publish_timer)
        self.identifier = self.settings['device_name'].replace(' ', '_').lower()
        self.state_topic = '{}/{}/state'.format(self.settings['topic'], self.identifier)

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
        if self.update_disks_list():
            if self.settings['homeassistant']:
                self.mqtt_send_config()
        payload.update(self.get_disk_usage())
        payload.update({"soc_temperature": self.get_temp()})
        self.mqtt_client.publish(topic=self.state_topic, payload=json.dumps(payload), qos=1, retain=False)

    def get_temp(self):
        # TODO: Add Raspberry Pi support
        self.logger.debug('Get SOC temperature')
        temp = '-1'
        try:
            temps = psutil.sensors_temperatures()
        except AttributeError:
            temps = {}
        if 'soc_thermal' in temps.keys():
            temp = str(temps['soc_thermal'][0].current)
        elif 'sun4i_ts' in temps.keys():
            temp = str(temps['sun4i_ts'][0].current)
        return temp

    def update_disks_list(self):
        update_config = False
        for disk in psutil.disk_partitions():
            if disk.mountpoint not in self.disks:
                self.disks.append(disk.mountpoint)
                update_config = True
        return update_config

    def get_disk_usage(self):
        self.logger.debug('Get disks usage')
        disks_payload = {}
        for disk in psutil.disk_partitions():
            if disk.mountpoint in self.disks:
                try:
                    disk_usage = str(psutil.disk_usage(disk.mountpoint).percent)
                except PermissionError:
                    disk_usage = '-1'
                disks_payload.update({
                    'disk_use_{}'.format(disk.mountpoint).replace('/', '_'): str(disk_usage)
                })
        return disks_payload

    def get_memory_usage(self):
        self.logger.debug('Get memory usage')
        return str(psutil.virtual_memory().percent)

    def mqtt_send_config(self):
        retain = True
        device_payload = {'device': {
            'identifiers': ['{}'.format(self.identifier)],
            'name': '{}'.format(self.settings['device_name']),
            'model': self.settings['model'],
            'manufacturer': self.settings['manufacturer']
        }
        }
        # SOC temperature.
        payload = {'name': '{} SOC temperature'.format(self.settings['device_name']),
                   'state_topic': self.state_topic,
                   'device_class': 'temperature',
                   'unit_of_measurement': '°C',
                   'value_template': '{{ value_json.soc_temperature }}',
                   'unique_id': '{}_sensor_soc_temperature'.format(self.identifier),
                   'json_attributes_topic': self.state_topic,
                   }
        payload.update(device_payload)
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/soc_temperature/config'.format(self.identifier),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        # Disks use.
        for disk in self.disks:
            disk_ = disk.replace('/', '_')
            payload = {'name': '{} Disk use {}'.format(self.settings['device_name'], disk),
                       'state_topic': self.state_topic,
                       'unit_of_measurement': '%',
                       'icon': 'mdi:harddisk',
                       'value_template': '{{{{ value_json.disk_use_{} }}}}'.format(disk_),
                       'unique_id': '{0}_sensor_disk_use_{1}'.format(self.identifier, disk_),
                       'json_attributes_topic': self.state_topic,
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/disk_use_{1}/config'.format(self.identifier, disk_),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
        # Memory use.
        payload = {'name': '{} Memory use'.format(self.settings['device_name']),
                   'state_topic': self.state_topic,
                   'unit_of_measurement': '%',
                   'icon': 'mdi:memory',
                   'value_template': '{{ value_json.memory_use }}',
                   'unique_id': '{}_sensor_memory_use'.format(self.identifier),
                   'json_attributes_topic': self.state_topic,
                   }
        payload.update(device_payload)
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/memory_use/config'.format(self.identifier),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        # Last boot.
        payload = {'device_class': 'timestamp',
                   'name': '{} Last boot'.format(self.settings['device_name']),
                   'state_topic': self.state_topic,
                   'icon': 'mdi:clock-start',
                   'value_template': '{{ value_json.last_boot }}',
                   'unique_id': '{}_sensor_last_boot'.format(self.identifier),
                   'json_attributes_topic': self.state_topic,
                   }
        payload.update(device_payload)
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/last_boot/config'.format(self.identifier),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        if self.settings['reboot/shutdown']:
            # Reboot switch.
            payload = {'name': '{} Reboot'.format(self.settings['device_name']),
                       'state_topic': '{}/{}/reboot'.format(self.settings['topic'], self.identifier),
                       'command_topic': '{}/{}/reboot'.format(self.settings['topic'], self.identifier),
                       'icon': 'mdi:restart',
                       'unique_id': '{}_reboot'.format(self.identifier)
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/switch/{0}/reboot/config'.format(self.identifier),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
            self.mqtt_client.publish(topic='{}/{}/reboot'.format(self.settings['topic'], self.identifier),
                                     payload='OFF', qos=1, retain=False)
            # Shutdown switch.
            payload = {'name': '{} Shutdown'.format(self.settings['device_name']),
                       'state_topic': '{}/{}/shutdown'.format(self.settings['topic'], self.identifier),
                       'command_topic': '{}/{}/shutdown'.format(self.settings['topic'], self.identifier),
                       'icon': 'mdi:power',
                       'unique_id': '{}_shutdown'.format(self.identifier)
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/switch/{0}/shutdown/config'.format(self.identifier),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
            self.mqtt_client.publish(topic='{}/{}/shutdown'.format(self.settings['topic'], self.identifier),
                                     payload='OFF', qos=1, retain=False)

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

    def on_message(self, client, userdata, message):
        self.logger.debug('Message received: {} = {}'.format(message.topic, message.payload))
        if message.topic == '{}/{}/reboot'.format(self.settings['topic'], self.identifier):
            if message.payload == b'ON':
                self.logger.info('Reboot command')
                system('reboot')
        elif message.topic == '{}}/{}/shutdown'.format(self.settings['topic'], self.identifier):
            if message.payload == b'ON':
                self.logger.info('Shutdown command')
                system('shutdown now -h')

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.debug('Connection to MQTT broker successful')
            self.update_disks_list()
            if self.settings['homeassistant']:
                self.mqtt_send_config()
                self.logger.debug('Sent config to MQTT broker')
            self.publish_timer = Timer(10, self.mqtt_publish_timer)
            self.publish_timer.start()
            if self.settings['reboot/shutdown']:
                # Subscribe reboot topic.
                (result, mid) = self.mqtt_client.subscribe('{}/{}/reboot'.format(self.settings['topic'],
                                                                                 self.identifier))
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.logger.debug('Successfully subscribed to reboot topic')
                else:
                    self.logger.error('Error subscribe to reboot topic')
                # Subscribe shutdown topic.
                (result, mid) = self.mqtt_client.subscribe('{}/{}/shutdown'.format(self.settings['topic'],
                                                                                   self.identifier))
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.logger.debug('Successfully subscribed to shutdown topic')
                else:
                    self.logger.error('Error subscribe to shutdown topic')
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

    def on_disconnect(self, client, userdata, rc):
        self.logger.debug('Disconnected from MQTT broker. {}'.format(rc))
        self.publish_timer.cancel()
        if self.settings['reboot/shutdown']:
            self.mqtt_client.unsubscribe('{}/{}/reboot'.format(self.settings['topic'], self.identifier))
            self.mqtt_client.unsubscribe('{}/{}/shutdown'.format(self.settings['topic'], self.identifier))

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
        self.mqtt_client.on_message = self.on_message
        self.logger.info('Connecting to MQTT broker on host {}:{}'.format(self.settings['mqtt']['hostname'],
                                                                          self.settings['mqtt']['port']))
        self.is_run = True
        self.mqtt_connect()
        self.logger.info('Connected to MQTT broker on host {}:{}'.format(self.settings['mqtt']['hostname'],
                                                                         self.settings['mqtt']['port']))
        self.mqtt_client.loop_start()
        while self.is_run:
            time.sleep(1)

    def stop(self):
        self.logger.info('Stopping')
        self.is_run = False
        self.publish_timer.cancel()
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
