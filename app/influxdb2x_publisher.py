from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
from flatten_json import flatten
from datetime import datetime


def print_config(config):

    logging.info("influxdb configuration:")
    for key, value in config.items():
        logging.info(f"\t{key} = {value}")


class InfluxdbPublisher:

    client: InfluxDBClient

    def connect(self):
        pass

    def __init__(self, config):
        print_config(config)
        self.client = InfluxDBClient(
            url=f"http://{config['host']}:{config['port']}",
            token=f"{config['token']}",
            org=f"{config['org']}")
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

        self.config = config

    def publish(self, json_payload: dict):

        try:
            point = Point("inverter_status").time(datetime.utcnow(),
                                                  WritePrecision.NS)
            point.tag("source", "selfa")
            flat = flatten(json_payload, separator='.')
            for key, value in flat.items():
                if isinstance(value, (int, float)):
                    point.field(key, value)
            self.write_api.write(bucket=self.config['bucket'],
                                 org=self.config['org'],
                                 record=point)
        except Exception as e:
            logging.error(f"Unable to send influxdb {e}")
