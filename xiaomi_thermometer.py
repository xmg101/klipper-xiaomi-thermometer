# Support for Xiaomi Bluetooth Thermometer via Mi Cloud
#
# Copyright (C) 2026  <your-name>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

DEFAULT_QUERY_INTERVAL = 5.0
XIAOMI_THERMOMETER_MODEL = "miaomiaoce.sensor_ht.t1"

class XiaomiThermometer:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name().split()[-1]

        self.mi_account = config.get("mi_account")
        self.mi_password = config.get("mi_password")
        # Mi Cloud accounts are region-locked: cn, de, us, ru, sg, etc.
        self.mi_country = config.get("mi_country", "cn")
        self.query_interval = config.getfloat(
            "query_interval", DEFAULT_QUERY_INTERVAL, minval=1.0
        )

        self.temp = self.humidity = 0.0
        self.min_temp = self.max_temp = 0.0
        self._callback = None
        self._device_did = None
        self._cloud = None

        self.printer.add_object("xiaomi_thermometer " + self.name, self)
        if self.printer.get_start_args().get("debugoutput") is not None:
            return
        self.sample_timer = self.reactor.register_timer(
            self._sample_temperature
        )
        self.printer.register_event_handler(
            "klippy:connect", self.handle_connect
        )

    def handle_connect(self):
        from micloud import MiCloud

        try:
            self._cloud = MiCloud(
                username=self.mi_account,
                password=self.mi_password,
                country=self.mi_country,
            )
            self._cloud.login()
            devices = self._cloud.get_devices()
        except Exception:
            logging.exception(
                "xiaomi_thermometer %s: Failed to login to Mi Cloud", self.name
            )
            raise self.printer.command_error(
                "xiaomi_thermometer %s: Mi Cloud login failed" % (self.name,)
            )

        for device in devices:
            model = device.get("model", "")
            if model == XIAOMI_THERMOMETER_MODEL:
                self._device_did = device.get("did")
                logging.info(
                    "xiaomi_thermometer %s: Found device %s (model=%s)",
                    self.name, self._device_did, model,
                )
                break

        if self._device_did is None:
            logging.warning(
                "xiaomi_thermometer %s: No thermometer found. "
                "Available devices: %s",
                self.name,
                [
                    (d.get("name"), d.get("model"), d.get("did"))
                    for d in devices
                ],
            )
            return

        self.reactor.update_timer(self.sample_timer, self.reactor.NOW)

    def setup_minmax(self, min_temp, max_temp):
        self.min_temp = min_temp
        self.max_temp = max_temp

    def setup_callback(self, cb):
        self._callback = cb

    def get_report_time_delta(self):
        return self.query_interval

    def _sample_temperature(self, eventtime):
        if self._device_did is None or self._cloud is None:
            return eventtime + self.query_interval

        try:
            data = self._cloud.get_device_data(self._device_did)
            if data:
                self.temp = float(data.get("temperature", self.temp))
                self.humidity = float(data.get("humidity", self.humidity))
        except Exception:
            logging.exception(
                "xiaomi_thermometer %s: Error querying device", self.name
            )
            return eventtime + self.query_interval

        # Chamber/environment sensor — warn on out-of-range
        # but do not halt printing (unlike heater thermistors).
        if self.temp < self.min_temp or self.temp > self.max_temp:
            logging.warning(
                "xiaomi_thermometer %s: temperature %.1f outside range "
                "%.1f:%.1f",
                self.name, self.temp, self.min_temp, self.max_temp,
            )

        if self._callback is not None:
            mcu = self.printer.lookup_object("mcu")
            measured_time = self.reactor.monotonic()
            self._callback(mcu.estimated_print_time(measured_time), self.temp)

        return eventtime + self.query_interval

    def get_status(self, eventtime):
        return {
            "temperature": round(self.temp, 2),
            "humidity": round(self.humidity, 2),
        }


def load_config(config):
    pheaters = config.get_printer().load_object(config, "heaters")
    pheaters.add_sensor_factory("xiaomi_thermometer", XiaomiThermometer)
