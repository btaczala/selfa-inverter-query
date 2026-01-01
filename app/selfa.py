import logging
import requests
import configparser
import json
import os
import tempfile
from jinja2 import Template
import selfa_crypt

base_url = 'https://lb.solinteg-cloud.com/'


class Selfa:
    config: configparser.SectionProxy

    def __init__(self, config: configparser.SectionProxy):
        self.config = config
        self.token = None
        self.default_token_path = os.path.join(tempfile.gettempdir(),
                                               "selfa-token.json")
        self.hw_info = {}
        self.read_token()
        if self.token is None:
            self.login()
        logging.debug(f"Creating selfa. token {self.token}")

        self.get_hw_info()

    def fetch(self, rest_of_url: str, name: str, retry: bool = False):
        logging.debug(f"fetching name {name} = {rest_of_url}")
        headers = {'token': f'{self.token}', 'lang': self.config['lang']}
        ret = requests.get(f'{base_url}/{rest_of_url}', headers=headers)
        j = ret.json()
        if j and 'errorCode' in j and 'info' in j:
            if j['info'] and 'code' in j['info']:
                if j['info']['code'] == 'error.10004' and not retry:
                    logging.info("Need to reauth")
                    self.reauth()
                    return self.fetch(rest_of_url, name, True)
                elif retry:
                    raise Exception(f'error {j['info']['code']} while retrying. Should never happen')
                else:
                    raise Exception(f'Unknown error {j['info']['code']} while fetching {rest_of_url}')
        else:
            raise Exception(f'Unknown error {j['info']['code']} while fetching {rest_of_url}')
        return j

    def reauth(self):
        os.remove(self.default_token_path)
        self.login()

    def list(self):
        return self.fetch('gen2api/app/owner/station/myList?searchFilter=',
                          "list")

    def get_hw_info(self):
        data = self.fetch(f'gen2api/pc/owner/inverter/current_info_plus/{self.config['serial']}', 'get_hw_info')
        self.hw_info = {
            "name": data['body'][0]['contents'][0]['value'],
            "sn": data['body'][0]['contents'][1]['value'],
            "model": data['body'][0]['contents'][3]['value'],
            "power": data['body'][0]['contents'][4]['value'],
            "software": data['body'][0]['contents'][5]['value']
        }
        logging.info(self.hw_info)

    def get_current_info(self):
        station = self.config['station']
        j = self.fetch(
            f'gen2api/pc/distributor/station/stationCurrentInfo/{station}/system?stationId={station}',
            'station_current_info')
        return j

    def get_current_info_plus(self):
        small_json = self.get_current_info()
        serial = self.config['serial']
        json = self.fetch(
            f'gen2api/pc/owner/inverter/current_info_plus/{serial}',
            'current_info_plus')

        json_formatted = {
            'pv': {
                'power': {
                    'value': small_json['body']['pvPower'],
                    'unit': small_json['body']['pvPowerUnit'],
                },
                'daily': {
                    'value': small_json['body']["powerGenerationToday"],
                    'unit': small_json['body']['powerGenerationTodayUnit'],
                },
                'total': {
                    'value': small_json['body']["cumulativePowerGeneration"],
                    'unit': small_json['body']['cumulativePowerGenerationUnit'],
                }
            },
            'home': {
                'total_power': small_json['body']['loadPower'],
                'power': {
                    'l1': json['body'][7]['contents'][0]['contents'][0]['value'],
                    'l2': json['body'][7]['contents'][0]['contents'][1]['value'],
                    'l3': json['body'][7]['contents'][0]['contents'][2]['value'],
                    'unit': json['body'][7]['contents'][0]['contents'][2]['unit'],
                }

            },
            'inverter': {
                'voltage': {
                    'l1': json['body'][2]['contents'][0]['contents'][0]['value'],
                    'l2': json['body'][2]['contents'][0]['contents'][1]['value'],
                    'l3': json['body'][2]['contents'][0]['contents'][2]['value'],
                    'unit': json['body'][2]['contents'][0]['contents'][2]['unit'],
                },
                'current': {
                    'l1': json['body'][2]['contents'][1]['contents'][0]['value'],
                    'l2': json['body'][2]['contents'][1]['contents'][1]['value'],
                    'l3': json['body'][2]['contents'][1]['contents'][2]['value'],
                    'unit': json['body'][2]['contents'][1]['contents'][2]['unit'],
                },
                'temperature': {
                    'value': json['body'][2]['contents'][8]['value'],
                    'unit': json['body'][2]['contents'][8]['unit'],
                },
                'battery': {
                    'power': {
                        'value': json['body'][4]['contents'][6]['value'],
                        'unit': json['body'][4]['contents'][6]['unit'],
                    },
                    'current': {
                        'value': json['body'][4]['contents'][7]['value'],
                        'unit': json['body'][4]['contents'][7]['unit'],
                    },
                    'voltage': {
                        'value': json['body'][4]['contents'][8]['value'],
                        'unit': json['body'][4]['contents'][8]['unit'],
                    },
                    'soc': json['body'][4]['contents'][9]['value'],
                    'soh': json['body'][4]['contents'][10]['value']
                }
            },
            'grid': {
                'total_power': small_json['body']['meterPower'],
                'power': {
                    'l1': json['body'][6]['contents'][0]['contents'][0]['value'],
                    'l2': json['body'][6]['contents'][0]['contents'][1]['value'],
                    'l3': json['body'][6]['contents'][0]['contents'][2]['value'],
                    'unit': json['body'][6]['contents'][0]['contents'][2]['unit'],
                }

            }

        }
        return json_formatted

    def read_token(self):
        try:
            with open(self.default_token_path, "r") as file:
                token_data = json.load(file)
                token = token_data.get("token")
                if token:
                    logging.info(
                        f"Token read successfully {token} from {self.default_token_path}"
                    )
                    self.token = token
                    return token
                else:
                    logging.error("Token not found in the file.")
                    return None
        except FileNotFoundError:
            logging.error("selfa-token.json file not found.")
            return None
        except json.JSONDecodeError:
            logging.error(
                "Error decoding JSON from selfa-token.json. Will try to reauth"
            )
            return None

    def login(self):
        json_payload = {
            'account': self.config["username"],
            'pwd': selfa_crypt.hash_password("", self.config["password"]),
        }
        logging.debug(f"payload is {json_payload}")
        headers = {
            'lang': self.config['lang'],
        }
        ret = requests.post(f'{base_url}/gen2api/pc/user/login',
                            headers=headers,
                            json=json_payload)
        if ret.json()['errorCode'] == 1:
            raise ConnectionError

        with open(self.default_token_path, "w") as file:
            data = {"token": ret.json()["body"][0]}
            json.dump(data, file)

        self.read_token()
