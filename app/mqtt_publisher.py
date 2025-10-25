import logging
import paho.mqtt.client as mqtt
import configparser
import json


class MqttPublisher:
    client: mqtt.Client
    config: configparser.SectionProxy

    def connect(self):
        self.client.on_connect = self.on_connect
        res = self.client.loop_start()
        logging.debug(f"Loop start={res}")
        self.client.connect(host=self.config['host'],
                            port=int(self.config['port']))

    def __init__(self, config):
        self.config = config
        self.client = mqtt.Client()
        self.connect()

    def set_topic(self, serial: str, station: str):
        self.topic = self.config['topic'] if 'topic' in self.config.keys(
        ) else "selfa/{station}/{serial}"

        self.topic = self.topic.replace("{station}", station)
        self.topic = self.topic.replace("{serial}", serial)

        logging.info(f"mqtt topic is {self.topic}")

    def publish(self, json_payload: dict):
        for v in json_payload:
            topic = self.topic + f"/{v}"
            self.client.publish(topic, json.dumps(json_payload[v]))

    def on_connect(self, client, userdata, flags, reason_code):
        logging.info(f"Connected to {self.config['host']}")
