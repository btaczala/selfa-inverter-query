import argparse
import os
import time
import logging
import json
import coloredlogs
import configparser
from selfa import Selfa
from stdout_publisher import StdOutPublished
from mqtt_publisher import MqttPublisher


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
                logging.info("Token read successfully.")
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
                        required=True,
                        help="Path to config file")
    parser.add_argument("--station",
                        type=str,
                        required=False,
                        help="Station id")
    parser.add_argument("--outputs",
                        type=str,
                        nargs='+',
                        choices=['mqtt', 'influxdb', 'stdout'],
                        required=False,
                        help="Output destination(s)")

    args = parser.parse_args()
    config = configparser.ConfigParser();
    config.read(args.config)
    coloredlogs.install(level='INFO',
                        fmt='%(asctime)s - %(levelname)s - %(message)s')

    # Your application logic here
    if not os.path.exists("selfa-token.json"):
        logging.info("selfa-token.json does not exists, authenticating first")
        fetch_token()
    publishers = []

    if 'stdout' in args.outputs:
        publishers.append(StdOutPublished())

    if 'mqtt' in args.outputs:
        if not args.mqtt_host:
            print("mqtt-host is required")
            exit(1)
        topic = args.mqtt_topic if args.mqtt_topic else f'selfa/{args.station}'
        publishers.append(
            MqttPublisher(host=args.mqtt_host,
                          port=args.mqtt_port,
                          topic=topic,
                          username=args.mqtt_username,
                          password=args.mqtt_password))

    if args.list:
        token = read_token()
        selfa = Selfa(token=token)

        print(selfa.list())
        exit(0)

    if not args.station:
        print("station is required")
        exit(1)

    # logging.info(f'{args.output}')

    while True:
        token = read_token()
        selfa = Selfa(token=token)

        data = selfa.get_current_info(args.station)

        for publisher in publishers:
            publisher.publish(data)
        time.sleep(args.timeout)


if __name__ == "__main__":
    main()
