#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime as dt
import json
from os import system, popen
from threading import Timer
import time
import fnmatch

import paho.mqtt.client as mqtt
import psutil
import pytz


class MainProcess(object):

    def __init__(self, logger_obj, settings_dict):
        self.settings = settings_dict
        self.logger = logger_obj
        self.disks = []
        self.devices = {}
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
        payload.update(self.get_disks())
        payload.update(self.get_devices())
        payload.update({"soc_temperature": self.get_temp()})
        self.mqtt_client.publish(topic=self.state_topic, payload=json.dumps(payload), qos=1, retain=False)
        self.mqtt_client.publish(topic='{}/{}/force_update'.format(self.settings['topic'], self.identifier),
                                 payload=b'OFF')

    def get_temp(self):
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
        elif 'cpu_thermal' in temps.keys():
            temp = str(temps['cpu_thermal'][0].current)
        return temp

    def update_disks_list(self):
        self.logger.debug('Update disks and disks devices lists')
        update_config = False
        for disk in psutil.disk_partitions():
            if disk.mountpoint not in self.disks:
                self.disks.append(disk.mountpoint)
                update_config = True
        try:
            data = popen('smartctl --scan')
            temp = data.read().split(' ')
            devices = fnmatch.filter(temp, '/dev/sd*')
            for device in devices:
                if len(device) >= 8:
                    device = device[:8]
                    data = popen('smartctl -i {}'.format(device))
                    res = data.read().splitlines()
                    for i in range(len(res)):
                        if 'Device Model' in res[i]:
                            temp = res[i].split(':')
                            if len(temp) == 2:
                                if temp[1] not in self.devices.keys():
                                    self.devices[temp[1]] = device
                                    update_config = True
                                else:
                                    if self.devices.get(temp[1], '') != device:
                                        self.devices[temp[1]] = device
        except:
            pass
        return update_config

    def get_disks(self):
        self.logger.debug('Get disks usage and total')
        disks_payload = {}
        for disk in psutil.disk_partitions():
            if disk.mountpoint in self.disks:
                try:
                    disk_usage = str(psutil.disk_usage(disk.mountpoint).percent)
                    disk_total = '{0:.1f}'.format(psutil.disk_usage(disk.mountpoint).total / 1048576)
                except PermissionError:
                    disk_usage = '0'
                    disk_total = '0'
                disk_ = disk.mountpoint.replace('/', '_')
                disk_ = disk_.replace(':\\', '')
                disks_payload.update({
                    'disk_use_{}'.format(disk_): str(disk_usage),
                    'disk_total_{}'.format(disk_): str(disk_total),
                })
        return disks_payload

    def get_devices(self):
        self.logger.debug('Get disks devices SMART')
        devices_payload = {}
        for device_name in self.devices.keys():
            device = self.devices[device_name]
            try:
                data = popen('smartctl --attributes {}'.format(device))
                res = data.read().splitlines()
                device_attr = {}
                for i in range(len(res)):
                    line = res[i].split()
                    if len(line) >= 10:
                        if line[1] == 'Temperature_Celsius':
                            device_attr['temperature'] = line[9]
                        elif line[1] == 'Power_Cycle_Count':
                            device_attr['power_cycle_count'] = line[9]
                        elif line[1] == 'Power_On_Hours':
                            device_attr['power_on_hours'] = line[9]
                        elif line[1] == 'Power_On_Hours_and_Msec':
                            values = line[9].split('+')
                            if len(values) > 1:
                                if 'h' in values[0]:
                                    device_attr['power_on_hours'] = values[0].replace('h', '')
                if device_attr:
                    device_name_ = device_name.replace(' ', '_').lower()
                    devices_payload.update({
                        'temperature_{}'.format(device_name_): str(device_attr.get('temperature', '-1')),
                        'power_cycle_count_{}'.format(device_name_): str(device_attr.get('power_cycle_count', '-1')),
                        'power_on_hours_{}'.format(device_name_): str(device_attr.get('power_on_hours', '-1')),
                    })
            except:
                self.logger.error('Error read SMART data for {}'.format(device_name))
        return devices_payload

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
                   'expire_after': self.settings['update_interval'] + 120,
                   }
        payload.update(device_payload)
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/soc_temperature/config'.format(self.identifier),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        # Disks use and total.
        for disk in self.disks:
            disk_ = disk.replace('/', '_')
            disk_ = disk_.replace(':\\', '')
            payload = {'name': '{} Disk use {}'.format(self.settings['device_name'], disk_),
                       'state_topic': self.state_topic,
                       'unit_of_measurement': '%',
                       'icon': 'mdi:harddisk',
                       'value_template': '{{{{ value_json.disk_use_{} }}}}'.format(disk_),
                       'unique_id': '{0}_sensor_disk_use_{1}'.format(self.identifier, disk_),
                       'json_attributes_topic': self.state_topic,
                       'expire_after': self.settings['update_interval'] + 120,
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/disk_use_{1}/config'.format(self.identifier, disk_),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
            payload = {'name': '{} Disk total {}'.format(self.settings['device_name'], disk_),
                       'state_topic': self.state_topic,
                       'unit_of_measurement': 'MB',
                       'icon': 'mdi:harddisk',
                       'value_template': '{{{{ value_json.disk_total_{} }}}}'.format(disk_),
                       'unique_id': '{0}_sensor_disk_total_{1}'.format(self.identifier, disk_),
                       'json_attributes_topic': self.state_topic,
                       'expire_after': self.settings['update_interval'] + 120,
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/disk_total_{1}/config'.format(self.identifier, disk_),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
        # Devices.
        for device_name in self.devices.keys():
            device_name_ = device_name.replace(' ', '_').lower()
            payload = {'name': '{} {} temperature'.format(self.settings['device_name'], device_name),
                       'state_topic': self.state_topic,
                       'unit_of_measurement': '°C',
                       'device_class': 'temperature',
                       'value_template': '{{{{ value_json.temperature_{} }}}}'.format(device_name_),
                       'unique_id': '{0}_sensor_temperature_{1}'.format(self.identifier, device_name_),
                       'json_attributes_topic': self.state_topic,
                       'expire_after': self.settings['update_interval'] + 120,
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/temperature_{1}/config'.format(self.identifier, device_name_),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
            payload = {'name': '{} {} Power Cycle Count'.format(self.settings['device_name'], device_name),
                       'state_topic': self.state_topic,
                       'unit_of_measurement': 'i',
                       'value_template': '{{{{ value_json.power_cycle_count_{} }}}}'.format(device_name_),
                       'unique_id': '{0}_sensor_power_cycle_count_{1}'.format(self.identifier, device_name_),
                       'json_attributes_topic': self.state_topic,
                       'expire_after': self.settings['update_interval'] + 120,
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/power_cycle_count_{1}/config'.format(self.identifier, device_name_),
                payload=json.dumps(payload),
                qos=1,
                retain=retain
            )
            payload = {'name': '{} {} Power On Hours'.format(self.settings['device_name'], device_name),
                       'state_topic': self.state_topic,
                       'unit_of_measurement': 'h',
                       'value_template': '{{{{ value_json.power_on_hours_{} }}}}'.format(device_name_),
                       'unique_id': '{0}_sensor_power_on_hours_{1}'.format(self.identifier, device_name_),
                       'json_attributes_topic': self.state_topic,
                       'expire_after': self.settings['update_interval'] + 120,
                       }
            payload.update(device_payload)
            self.mqtt_client.publish(
                topic='homeassistant/sensor/{0}/power_on_hours_{1}/config'.format(self.identifier, device_name_),
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
                   'expire_after': self.settings['update_interval'] + 120,
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
                   'expire_after': self.settings['update_interval'] + 120,
                   }
        payload.update(device_payload)
        self.mqtt_client.publish(
            topic='homeassistant/sensor/{0}/last_boot/config'.format(self.identifier),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        # Force update switch.
        payload = {'name': '{} Force update'.format(self.settings['device_name']),
                   'state_topic': '{}/{}/force_update'.format(self.settings['topic'], self.identifier),
                   'command_topic': '{}/{}/force_update'.format(self.settings['topic'], self.identifier),
                   'unique_id': '{}_force_update'.format(self.identifier)
                   }
        payload.update(device_payload)
        self.mqtt_client.publish(
            topic='homeassistant/switch/{0}/force_update/config'.format(self.identifier),
            payload=json.dumps(payload),
            qos=1,
            retain=retain
        )
        self.mqtt_client.publish(topic='{}/{}/force_update'.format(self.settings['topic'], self.identifier),
                                 payload='OFF', qos=1, retain=False)
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
                try:
                    system('reboot')
                except:
                    self.logger.error('Error reboot')
        elif message.topic == '{}/{}/shutdown'.format(self.settings['topic'], self.identifier):
            if message.payload == b'ON':
                self.logger.info('Shutdown command')
                try:
                    system('shutdown now -h')
                except:
                    self.logger.error('Error shutdown')
        elif message.topic == '{}/{}/force_update'.format(self.settings['topic'], self.identifier):
            if message.payload == b'ON':
                self.logger.debug('Force update command')
                try:
                    self.publish_timer.cancel()
                except:
                    self.logger.error('Error cancel publish timer')
                self.mqtt_publish_timer()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.debug('Connection to MQTT broker successful')
            self.update_disks_list()
            if self.settings['homeassistant']:
                self.mqtt_send_config()
                self.logger.debug('Sent config to MQTT broker')
            self.publish_timer = Timer(10, self.mqtt_publish_timer)
            self.publish_timer.start()
            # Subscribe force update topic.
            (result, mid) = self.mqtt_client.subscribe('{}/{}/force_update'.format(self.settings['topic'],
                                                                                   self.identifier))
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug('Successfully subscribed to force update topic')
            else:
                self.logger.error('Error subscribe to force update topic')
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
