#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.handlers
import signal
import sys
import time

from sys_sensors_mqtt import MainProcess
from sys_sensors_settings import Settings


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


def sigterm_handler(_signo, _stack_frame):
    logger.info('Received signal {}, stop service'.format(_signo))
    app.stop()


if __name__ == "__main__":
    logger = logging.Logger('SysSensorsMQTT')

    formatter = logging.Formatter('%(filename)-25s|%(lineno)4d|%(levelname)-7s|%(asctime)-23s|%(message)s')

    settings = Settings(logger)
    settings.read_settings()

    handler_infos = logging.handlers.RotatingFileHandler(settings.settings['log_file'], maxBytes=1000000, backupCount=1)
    handler_infos.setFormatter(formatter)

    logger.addHandler(handler_infos)

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
