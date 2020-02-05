#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.handlers
import signal
import sys
import time

from pytz import timezone
import yaml

from sys_sensors_mqtt import MainProcess


class App:
    
    def __init__(self, logger_obj, settings_dict):
        self.logger = logger_obj
        self.main_process = None
        self.is_run = False
        self.settings = settings_dict
            
    def run(self):
        self.main_process = MainProcess(self.logger, self.settings)
        self.is_run = True
        i = 1
        timer = time.time()
        while self.is_run:
            self.logger.info('Start SysSensorsMQTT')
            if time.time() - timer < 10 and i == 3:
                self.logger.error('Too much runs. END')
                self.is_run = False
                break
            elif time.time() - timer > 10000:
                i = 2
                timer = time.time()
            else:
                timer = time.time()
            try:
                self.main_process.run()
            except SystemExit:
                pass
            except:
                self.logger.error(sys.exc_info())
            self.logger.info('End SysSensorsMQTT')
            i += 1

    def stop(self):
        if self.main_process is not None and self.is_run:
            self.logger.info('SysSensorsMQTT stop')
            self.is_run = False
            self.main_process.stop()
            sys.exit()
        else:
            self.logger.warning('SysSensorsMQTT not started')

        
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
        if 'port' not in self.settings['mqtt']:
            self.settings['mqtt']['port'] = 1883
        else:
            self.settings['mqtt']['port'] = int(self.settings['mqtt']['port'])
        if 'user' not in self.settings['mqtt']:
            self.settings['mqtt']['user'] = ''
        if 'password' not in self.settings['mqtt']:
            self.settings['mqtt']['password'] = ''
        if 'timezone' not in self.settings:
            self.settings['timezone'] = 'Europe/Moscow'
        self.settings['timezone'] = timezone(self.settings["timezone"])
        if 'device_name' not in self.settings:
            self.settings['device_name'] = 'Device1'
        if 'client_id' not in self.settings:
            self.settings['client_id'] = 'client1'
        if 'model' not in self.settings:
            self.settings['model'] = 'model'
        if 'manufacturer' not in self.settings:
            self.settings['manufacturer'] = 'manufacturer'
        if 'update_interval' not in self.settings:
            self.settings['update_interval'] = 300.
        else:
            self.settings['update_interval'] = int(self.settings['update_interval'])
        if 'reboot/shutdown' not in self.settings:
            self.settings['reboot/shutdown'] = False
        else:
            if self.settings['reboot/shutdown'] is not True:
                self.settings['reboot/shutdown'] = False
    
    def read_settings(self):
        with open('settings.yaml') as f:
            try:
                self.settings = yaml.safe_load(f)
            except yaml.YAMLError:
                self.logger.info('Some error in settings file')
                self.settings = {}
        self.check_settings()


def sigterm_handler(_signo, _stack_frame):
    logger.info('Received signal {}, stop service'.format(_signo))
    app.stop()


if __name__ == "__main__":
    logger = logging.Logger('SysSensorsMQTT')

    formatter = logging.Formatter('%(filename)-25s|%(lineno)4d|%(levelname)-7s|%(asctime)-23s|%(message)s')

    handler_infos = logging.handlers.RotatingFileHandler("/var/log/sys_sensors_mqtt.log", maxBytes=1000000,
                                                         backupCount=1)
    handler_infos.setFormatter(formatter)

    logger.addHandler(handler_infos)

    settings = Settings(logger)
    settings.read_settings()

    if settings.settings['logging_level'] == 'DEBUG':
        handler_infos.setLevel(logging.DEBUG)
    elif settings.settings['logging_level'] == 'INFO':
        handler_infos.setLevel(logging.INFO)
    else:
        handler_infos.setLevel(logging.ERROR)

    app = App(logger, settings.settings)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    app.run()
