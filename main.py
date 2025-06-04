import argparse
import os
import time
import logging
import json
import coloredlogs
import configparser
from selfa import Selfa
from stdout_publisher import StdOutPublished


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
    coloredlogs.install(level='INFO',
                        fmt='%(asctime)s - %(levelname)s - %(message)s')

    if 'stdout' in config.sections():
        publishers.append(StdOutPublished())

    if not config['selfa']['station']:
        print("station is required")
        exit(1)

    while True:
        token = read_token()
        selfa = Selfa(token=token)

        data = []

        # data.append(selfa.get_current_info(config['selfa']['station']))
        data.append(selfa.get_grid_voltage_level(config['selfa']['serial']))

        for publisher in publishers:
            for d in data:
                publisher.publish(d)
        time.sleep(args.timeout)


if __name__ == "__main__":
    main()
