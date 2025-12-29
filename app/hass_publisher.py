from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import Sensor, SensorInfo
import configparser
import logging


class HomeAssistantPublisher:
    mqtt_settings: Settings.MQTT
    config: configparser.SectionProxy
    device_info: DeviceInfo
    current_power: Sensor
    current_total_load: Sensor
    battery_soc: Sensor
    battery_power: Sensor
    l_voltages: [Sensor, Sensor, Sensor]
    l_powers: [Sensor, Sensor, Sensor]

    def create_battery(self):
        s_info = SensorInfo(name="battery_soc", device_class="battery", display_name="Battery SoC", force_update=True,
                            unit_of_measurement="%", device=self.device_info, unique_id=self.config['selfa']['station'] + "-battery_soc",
                            state_class="measurement")

        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.battery_soc = Sensor(settings)

        s_info = SensorInfo(name="current_battery_power", device_class="power", display_name="Battery power", force_update=True,
                            unit_of_measurement="kW", device=self.device_info, unique_id=self.config['selfa']['station'] + "-battery_power", state_class="measurement")
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.battery_power = Sensor(settings)

    def create_current_pv_power(self):
        s_info = SensorInfo(name="current_power_production", device_class="power", display_name="Current power production", force_update=True,
                            unit_of_measurement="kW", device=self.device_info, unique_id=self.config['selfa']['station'] + "-power", state_class="measurement")
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.current_power = Sensor(settings)

    def create_current_total_load(self):
        s_info = SensorInfo(name="current_total_load", device_class="power", display_name="Current total load", force_update=True,
                            unit_of_measurement="kW", device=self.device_info, unique_id=self.config['selfa']['station'] + "-total-load", state_class="measurement", icon="mdi:meter-electric")
        settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
        self.current_total_load = Sensor(settings)

    def create_l_voltages(self):
        self.l_voltages = [Sensor, Sensor, Sensor]
        for idx, l_voltage in enumerate(self.l_voltages):
            s_info = SensorInfo(name=f"l{idx + 1}_voltage", device_class="voltage", display_name=f"L{idx + 1} voltage", force_update=True,
                                unit_of_measurement="V", device=self.device_info, unique_id=self.config['selfa']['station'] + f"-l{idx + 1}_voltage", state_class="measurement")
            settings = Settings(mqtt=self.mqtt_settings, entity=s_info)
            self.l_voltages[idx] = Sensor(settings)

    def __init__(self, config, hw_info):
        self.config = config
        self.mqtt_settings = Settings.MQTT(host=self.config['homeassistant']['host'],
                                           port=int(self.config['homeassistant']['port']), state_prefix=self.config['homeassistant'].get('prefix', 'hmd'))
        self.device_info = DeviceInfo(name=self.config['homeassistant']['name'], identifiers=self.config['selfa']['station'], model = hw_info['model'], manufacturer="Selfa", sw_version=hw_info['software'])

        self.create_current_pv_power()
        self.create_current_total_load()
        self.create_battery()
        self.create_l_voltages()

    def publish(self, json_payload: dict):
        logging.info(f'homeassistant publish {json_payload}')
        self.current_power.set_state(json_payload['inverter']['pv']['power'])
        self.current_total_load.set_state(json_payload['inverter']['meter']['power'] * -1)
        self.battery_soc.set_state(json_payload['inverter']['battery']['level'])
        self.battery_power.set_state(json_payload['inverter']['battery']['power'])

        for idx, v in enumerate(self.l_voltages):
            v.set_state(json_payload['grid']['voltage'][f'l{idx + 1}'])
