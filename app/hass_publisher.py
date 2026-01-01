from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import Sensor, SensorInfo
import configparser
import logging
from typing import List


class HomeAssistantPublisher:
    mqtt_settings: Settings.MQTT
    config: configparser.SectionProxy
    device_info: DeviceInfo
    current_power: Sensor
    current_total_load: Sensor
    current_grid_usage: Sensor
    pv_daily: Sensor
    pv_total: Sensor
    battery_soc: Sensor
    battery_power: Sensor
    l_voltages: List[Sensor]
    l_powers: List[Sensor]

    def create_battery(self):
        s_info = SensorInfo(
            name="battery_soc",
            device_class="battery",
            display_name="Battery SoC",
            force_update=True,
            unit_of_measurement="%",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-battery_soc",
            state_class="measurement",
        )

        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.battery_soc = Sensor(settings)

        s_info = SensorInfo(
            name="current_battery_power",
            device_class="power",
            display_name="Battery power",
            force_update=True,
            unit_of_measurement="kW",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-battery_power",
            state_class="measurement",
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.battery_power = Sensor(settings)

    def create_current_pv_power(self):
        s_info = SensorInfo(
            name="current_power_production",
            device_class="power",
            display_name="Current power production",
            force_update=True,
            unit_of_measurement="kW",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-power",
            state_class="measurement",
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.current_power = Sensor(settings)

    def create_current_total_load(self):
        s_info = SensorInfo(
            name="current_total_load",
            device_class="power",
            display_name="Current total load",
            force_update=True,
            unit_of_measurement="kW",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-total-load",
            state_class="measurement",
            icon="mdi:meter-electric",
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.current_total_load = Sensor(settings)

    def create_current_grid_usage(self):
        s_info = SensorInfo(
            name="current_grid_usage",
            device_class="power",
            display_name="Current grid usage",
            force_update=True,
            unit_of_measurement="kW",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-grid-usage",
            state_class="measurement",
            icon="mdi:transmission-tower",
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.current_grid_usage = Sensor(settings)

    def create_pv_daily(self):
        s_info = SensorInfo(
            name="pv_daily_production",
            device_class="energy",
            display_name="PV Daily Production",
            force_update=True,
            unit_of_measurement="kWh",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-pv-daily",
            state_class="measurement",
            icon="mdi:solar-power",
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.pv_daily = Sensor(settings)

    def create_pv_total(self):
        s_info = SensorInfo(
            name="pv_total_production",
            device_class="energy",
            display_name="PV Total Production",
            force_update=True,
            unit_of_measurement="kWh",
            device=self.device_info,
            unique_id=self.config["selfa"]["station"] + "-pv-total",
            state_class="total_increasing",
            icon="mdi:solar-power",
        )
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.pv_total = Sensor(settings)

    def create_l_voltages(self):
        self.l_voltages = []
        for idx in range(3):
            s_info = SensorInfo(
                name=f"l{idx + 1}_voltage",
                device_class="voltage",
                display_name=f"L{idx + 1} voltage",
                force_update=True,
                unit_of_measurement="V",
                device=self.device_info,
                unique_id=self.config["selfa"]["station"] + f"-l{idx + 1}_voltage",
                state_class="measurement",
            )
            settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
            self.l_voltages.append(Sensor(settings))

    def create_l_powers(self):
        self.l_powers = []
        for idx in range(3):
            s_info = SensorInfo(
                name=f"l{idx + 1}_power",
                device_class="power",
                display_name=f"Grid L{idx + 1} power",
                force_update=True,
                unit_of_measurement="kW",
                device=self.device_info,
                unique_id=self.config["selfa"]["station"] + f"-l{idx + 1}_power",
                state_class="measurement",
            )
            settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
            self.l_powers.append(Sensor(settings))

    def __init__(self, config, hw_info):
        self.config = config
        self.mqtt_settings = Settings.MQTT(
            host=self.config["homeassistant"]["host"],
            port=int(self.config["homeassistant"]["port"]),
            state_prefix=self.config["homeassistant"].get("prefix", "hmd"),
        )
        self.device_info = DeviceInfo(
            name=self.config["homeassistant"]["name"],
            identifiers=self.config["selfa"]["station"],
            model=hw_info["model"],
            manufacturer="Selfa",
            sw_version=hw_info["software"],
        )

        self.create_current_pv_power()
        self.create_current_total_load()
        self.create_current_grid_usage()
        self.create_pv_daily()
        self.create_pv_total()
        self.create_battery()
        self.create_l_voltages()
        self.create_l_powers()

    def publish(self, json_payload: dict):
        logging.info(f"homeassistant publish {json_payload}")
        self.current_power.set_state(json_payload["pv"]["power"]["value"])
        self.current_total_load.set_state(json_payload["home"]["total_power"])
        self.current_grid_usage.set_state(json_payload["grid"]["total_power"])
        self.pv_daily.set_state(json_payload["pv"]["daily"]["value"])
        self.pv_total.set_state(json_payload["pv"]["total"]["value"])
        self.battery_soc.set_state(json_payload["inverter"]["battery"]["soc"])
        self.battery_power.set_state(
            json_payload["inverter"]["battery"]["power"]["value"]
        )
        #
        for idx, v in enumerate(self.l_voltages):
            v.set_state(json_payload["inverter"]["voltage"][f"l{idx + 1}"])
        for idx, p in enumerate(self.l_powers):
            p.set_state(json_payload["grid"]["power"][f"l{idx + 1}"])
