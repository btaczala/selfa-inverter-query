import logging
import requests
import configparser
import json
from jinja2 import Template

base_url = 'https://lb.solinteg-cloud.com/'

specification_current = '''
{
    "inverter": {
        "pv": {
            "power": {{body.pvPower}},
            "unit": "{{body.pvPowerUnit}}"
        },
        "today": {
            "power": {{body.powerGenerationToday}},
            "unit": "{{body.powerGenerationTodayUnit}}"
        },
        "battery": {
            "level": {{body.soc}},
            "power": {{body.batteryPower}}
        },
        "meter": {
            "power": {{body.meterPower}},
            "unit": "{{body.meterPowerUnit}}"
        }
    }
}
'''


class Selfa:
    config: configparser.SectionProxy

    def __init__(self, config: configparser.SectionProxy):
        self.token = self.read_token()
        self.config = config
        logging.debug(f"Creating selfa. token {self.token}")

    def fetch(self, rest_of_url: str):
        headers = {'token': f'{self.token}', 'lang': self.config['lang']}
        ret = requests.get(f'{base_url}/{rest_of_url}', headers=headers)
        return ret.json()

    def list(self):
        return self.fetch('gen2api/app/owner/station/myList?searchFilter=')

    def get_current_info(self):
        station = self.config['station']
        j = self.fetch(
            f'gen2api/pc/distributor/station/stationCurrentInfo/{station}/system?stationId={station}'
        )

        template = Template(specification_current)
        renderer = template.render(**j)
        logging.debug(renderer)
        return json.loads(renderer)

    def get_grid_voltage_level(self):
        serial = self.config['serial']
        json = self.fetch(
            f'gen2api/pc/owner/inverter/current_info_plus/{serial}')

        return {
            'grid': {
                'l1': json['body'][2]['contents'][0]['contents'][0]['value'],
                'l2': json['body'][2]['contents'][0]['contents'][1]['value'],
                'l3': json['body'][2]['contents'][0]['contents'][2]['value'],
            }
        }

    def read_token(self):
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
