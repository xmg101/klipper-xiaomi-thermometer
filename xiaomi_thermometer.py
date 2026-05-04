# Support for Xiaomi Bluetooth Thermometer via Mi Cloud
#
# Copyright (C) 2026
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import hashlib
import logging
import requests

KELVIN_TO_CELSIUS = -273.15
DEFAULT_QUERY_INTERVAL = 5.0
XIAOMI_THERMOMETER_MODEL = "miaomiaoce.sensor_ht.t1"


class MiCloudClient:
    def __init__(self, username, password, country="cn"):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/94.0.4606.85 Mobile Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
            }
        )
        self.username = username
        self.password = password
        self.country = country
        self.user_id = None
        self._logged_in = False

    def _hash_password(self):
        return hashlib.md5(self.password.encode()).hexdigest().upper()

    def login(self):
        # Step 1: Get sign token
        sign_url = (
            "https://account.xiaomi.com/pass/serviceLogin"
            "?sid=miaov5&_json=true"
        )
        resp = self.session.get(sign_url)
        resp.raise_for_status()
        sign_data = resp.json()
        _sign = sign_data.get("_sign", "")
        qs = sign_data.get("qs", "")
        callback = sign_data.get("callback", "")

        # Step 2: Submit login credentials
        login_url = "https://account.xiaomi.com/pass/serviceLoginAuth2"
        payload = {
            "sid": "miaov5",
            "qs": qs,
            "callback": callback,
            "_sign": _sign,
            "_json": "true",
            "user": self.username,
            "hash": self._hash_password(),
        }
        resp = self.session.post(login_url, data=payload)
        resp.raise_for_status()
        result = resp.json()

        ssecurity = result.get("ssecurity")
        self.user_id = result.get("userId")
        location = result.get("location")
        code = result.get("code", 0)

        if code != 0 or not ssecurity:
            desc = result.get("desc", "unknown error")
            raise RuntimeError(f"Login failed: {desc} (code={code})")

        # Step 3: Store ssecurity and follow redirect for serviceToken
        self.session.cookies.set("userId", str(self.user_id))
        self.session.cookies.set("ssecurity", ssecurity)

        if location:
            resp = self.session.get(location)
            resp.raise_for_status()

        self._logged_in = True
        return True

    def get_devices(self):
        url = "https://api.io.mi.com/app/home/device_list"
        resp = self.session.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("list", [])

    def get_device_data(self, did):
        url = "https://api.io.mi.com/app/miotspec/prop/get"
        params = {"did": did}
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        result = {}
        for prop in data.get("result", []):
            siid = prop.get("siid")
            piid = prop.get("piid")
            value = prop.get("value")

            if siid == 2 and piid == 1:  # Temperature, value in 0.01C
                result["temperature"] = float(value) / 100.0
            elif siid == 2 and piid == 2:  # Humidity, value in 0.01%
                result["humidity"] = float(value) / 100.0
            elif siid == 3 and piid == 1:  # Battery
                result["battery"] = float(value)

        return result


class XiaomiThermometer:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name().split()[-1]

        self.mi_account = config.get("mi_account")
        self.mi_password = config.get("mi_password")
        self.mi_country = config.get("mi_country", "cn")
        self.query_interval = config.getfloat(
            "query_interval", DEFAULT_QUERY_INTERVAL, minval=1.0
        )
        self.min_temp = config.getfloat(
            "min_temp", KELVIN_TO_CELSIUS, minval=KELVIN_TO_CELSIUS
        )
        self.max_temp = config.getfloat(
            "max_temp", 99999999.9, above=self.min_temp
        )

        self.temp = self.humidity = 0.0
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
        try:
            self._cloud = MiCloudClient(
                username=self.mi_account,
                password=self.mi_password,
                country=self.mi_country,
            )
            self._cloud.login()
            devices = self._cloud.get_devices()
        except Exception:
            logging.exception(
                "xiaomi_thermometer %s: Failed to login to Mi Cloud",
                self.name,
            )
            raise self.printer.command_error(
                "xiaomi_thermometer %s: Mi Cloud login failed"
                % (self.name,)
            )

        for device in devices:
            model = device.get("model", "")
            if model == XIAOMI_THERMOMETER_MODEL:
                self._device_did = device.get("did")
                logging.info(
                    "xiaomi_thermometer %s: Found device %s (model=%s)",
                    self.name,
                    self._device_did,
                    model,
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
                if "temperature" in data:
                    self.temp = data["temperature"]
                if "humidity" in data:
                    self.humidity = data["humidity"]
        except Exception:
            logging.exception(
                "xiaomi_thermometer %s: Error querying device",
                self.name,
            )
            return eventtime + self.query_interval

        # Chamber/environment sensor — warn on out-of-range
        # but do not halt printing (unlike heater thermistors).
        if self.temp < self.min_temp or self.temp > self.max_temp:
            logging.warning(
                "xiaomi_thermometer %s: temperature %.1f outside range "
                "%.1f:%.1f",
                self.name,
                self.temp,
                self.min_temp,
                self.max_temp,
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


def load_config_prefix(config):
    return XiaomiThermometer(config)
