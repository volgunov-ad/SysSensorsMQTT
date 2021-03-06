#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pytz import timezone
import yaml


class Settings(object):

    def __init__(self, logger_obj, file='settings.yaml'):
        self.settings_file = file
        self.settings = {}
        self.logger = logger_obj

    def check_settings(self):
        if 'mqtt' not in self.settings:
            self.settings['mqtt'] = {}
        elif not isinstance(self.settings['mqtt'], dict):
            self.settings['mqtt'] = {}
        if 'hostname' not in self.settings['mqtt']:
            self.settings['mqtt']['hostname'] = '127.0.0.1'
        else:
            if self.settings['mqtt']['hostname'] is None:
                self.settings['mqtt']['hostname'] = '127.0.0.1'
        if 'port' not in self.settings['mqtt']:
            self.settings['mqtt']['port'] = 1883
        else:
            if self.settings['mqtt']['port'] is None:
                self.settings['mqtt']['port'] = 1883
            else:
                self.settings['mqtt']['port'] = int(self.settings['mqtt']['port'])
        if 'user' not in self.settings['mqtt']:
            self.settings['mqtt']['user'] = ''
        else:
            if self.settings['mqtt']['user'] is None:
                self.settings['mqtt']['user'] = ''
        if 'password' not in self.settings['mqtt']:
            self.settings['mqtt']['password'] = ''
        else:
            if self.settings['mqtt']['password'] is None:
                self.settings['mqtt']['password'] = ''
        if 'timezone' not in self.settings:
            self.settings['timezone'] = 'Europe/Moscow'
        else:
            if self.settings['timezone'] is None:
                self.settings['timezone'] = 'Europe/Moscow'
        self.settings['timezone'] = timezone(self.settings["timezone"])
        if 'device_name' not in self.settings:
            self.settings['device_name'] = 'Device1'
        else:
            if self.settings['device_name'] is None:
                self.settings['device_name'] = 'Device1'
        if 'client_id' not in self.settings:
            self.settings['client_id'] = 'client1'
        else:
            if self.settings['client_id'] is None:
                self.settings['client_id'] = 'client1'
        if 'model' not in self.settings:
            self.settings['model'] = 'model'
        else:
            if self.settings['model'] is None:
                self.settings['model'] = 'model'
        if 'manufacturer' not in self.settings:
            self.settings['manufacturer'] = 'manufacturer'
        else:
            if self.settings['manufacturer'] is None:
                self.settings['manufacturer'] = 'manufacturer'
        if 'update_interval' not in self.settings:
            self.settings['update_interval'] = 300.
        else:
            if self.settings['update_interval'] is None:
                self.settings['update_interval'] = 300.
            else:
                self.settings['update_interval'] = int(self.settings['update_interval'])
        if 'reboot/shutdown' not in self.settings:
            self.settings['reboot/shutdown'] = False
        else:
            if self.settings['reboot/shutdown'] is not True:
                self.settings['reboot/shutdown'] = False
        if 'log_file' not in self.settings:
            self.settings['log_file'] = '/var/log/sys_sensors_mqtt.log'
        else:
            if self.settings['log_file'] is None:
                self.settings['log_file'] = '/var/log/sys_sensors_mqtt.log'
        if 'homeassistant' not in self.settings:
            self.settings['homeassistant'] = False
        else:
            if self.settings['homeassistant'] is not True:
                self.settings['homeassistant'] = False
        if 'topic' not in self.settings:
            self.settings['topic'] = 'devices'
        else:
            if self.settings['topic'] is None:
                self.settings['topic'] = 'devices'

    def read_settings(self):
        try:
            with open('settings.yaml') as f:
                try:
                    self.settings = yaml.safe_load(f)
                except yaml.YAMLError:
                    self.settings = {}
        except FileNotFoundError:
            self.settings = {}
        self.check_settings()
