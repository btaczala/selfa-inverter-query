import argparse
import time
import sys
import logging
import configparser
import os
from colorlog import ColoredFormatter
from selfa import Selfa
from stdout_publisher import StdOutPublished
from mqtt_publisher import MqttPublisher
from influxdb2x_publisher import InfluxdbPublisher


def print_config(config):
    logging.info("mqtt configuration:")
    for key, value in config.items():
        logging.info(f"\t{key} = {value}")


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

    publishers = []

    config = configparser.ConfigParser()

    if not args.config:
        print("provide path to config file")
        exit(1)

    logging.basicConfig(level=args.log_level,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    if not os.path.exists(args.config):
        logging.error(f"Path {args.config} does not exists")
        exit(1)

    config.read(args.config)

    if args.list:
        selfa = Selfa(config['selfa'])
        print(selfa.list())
        exit(0)

    if args.timeout < 5:
        logging.warn(
            f"Timeout {args.timeout} is smaller than 5. This does not make sense as Selfa updates every 5 seconds "
        )

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
        print_config(config["mqtt"])
        try:
            mqtt = MqttPublisher(config['mqtt'])
            mqtt.set_topic(serial=config['selfa']['serial'],
                           station=config['selfa']['station'])
            publishers.append(mqtt)
        except Exception as e:
            logging.error(f"Unable to create mqtt config.{e}")

    if 'influxdb' in config.sections():
        publisher = InfluxdbPublisher(config['influxdb'])
        publishers.append(publisher)

    if not config['selfa']['station']:
        print("station is required")
        exit(1)
    selfa = Selfa(config['selfa'])

    while True:
        try:
            data = []
            data.append(selfa.get_current_info())
            data.append(selfa.get_grid_voltage_level())

            for publisher in publishers:
                for d in data:
                    publisher.publish(d)
            time.sleep(args.timeout)
        except Exception as e:
            logging.error(f'Unknown error {e}')
            sys.exit(1)


if __name__ == "__main__":
    main()
