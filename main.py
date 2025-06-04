import argparse
import os
import time
import logging
import json
import configparser
from colorlog import ColoredFormatter
from selfa import Selfa
from stdout_publisher import StdOutPublished
from mqtt_publisher import MqttPublisher
from influxdb2x_publisher import InfluxdbPublisher


def print_config(config):

    logging.info("mqtt configuration:")
    for key, value in config.items():
        logging.info(f"\t{key} = {value}")


def fetch_token():
    # Placeholder for the token retrieval logic
    print("Retrieving token...")


def get_data(token: str):
    pass


def read_token():
    try:
        with open("selfa-token.json", "r") as file:
            token_data = json.load(file)
            token = token_data.get("token")
            if token:
                logging.debug("Token read successfully.")
                return token
            else:
                logging.error("Token not found in the file.")
                return None
    except FileNotFoundError:
        logging.error("selfa-token.json file not found.")
        return None
    except json.JSONDecodeError:
        logging.error("Error decoding JSON from selfa-token.json.")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Description of your application.")
    parser.add_argument("--timeout",
                        type=int,
                        default=5,
                        help="Timeout in seconds between actions")
    parser.add_argument("--list", action="store_true", help="List stations")
    parser.add_argument("--config",
                        type=str,
                        required=False,
                        help="Path to config file")

    parser.add_argument("--log-level",
                        default=logging.INFO,
                        type=lambda x: getattr(logging, x))
    args = parser.parse_args()

    if not os.path.exists("selfa-token.json"):
        fetch_token()
    publishers = []

    if args.list:
        token = read_token()
        selfa = Selfa(token=token)
        print(selfa.list())
        exit(0)

    config = configparser.ConfigParser()
    config.read(args.config)

    logging.basicConfig(level=args.log_level,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%')
    handler.setFormatter(formatter)

    if 'stdout' in config.sections():
        publishers.append(StdOutPublished())

    if 'mqtt' in config.sections():
        # logging.info(f'Creating mqtt with config={config["mqtt"]}')
        print_config(config["mqtt"])
        mqtt = MqttPublisher(config['mqtt'])
        mqtt.set_topic(serial=config['selfa']['serial'],
                       station=config['selfa']['station'])
        publishers.append(mqtt)

    if 'influxdb' in config.sections():
        publisher = InfluxdbPublisher(config['influxdb'])
        publishers.append(publisher)

    if not config['selfa']['station']:
        print("station is required")
        exit(1)

    while True:
        token = read_token()
        selfa = Selfa(token=token)

        data = []

        data.append(selfa.get_current_info(config['selfa']['station']))
        data.append(selfa.get_grid_voltage_level(config['selfa']['serial']))

        for publisher in publishers:
            for d in data:
                publisher.publish(d)
        time.sleep(args.timeout)


if __name__ == "__main__":
    main()
