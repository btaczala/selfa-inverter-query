import logging
import requests
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

    def __init__(self, token):
        self.token = token
        logging.debug(f"Creating selfa. token {self.token}")

    def fetch(self, rest_of_url: str, token: str):
        headers = {'token': f'{token}', 'lang': 'PL_PL'}
        ret = requests.get(f'{base_url}/{rest_of_url}', headers=headers)

        return ret.json()

    def list(self):
        return self.fetch('gen2api/app/owner/station/myList?searchFilter=',
                          self.token)

    def get_current_info(self, stationId: str):
        j = self.fetch(
            f'gen2api/pc/distributor/station/stationCurrentInfo/{stationId}/system?stationId={stationId}',
            self.token)

        template = Template(specification_current)
        renderer = template.render(**j)
        logging.debug(renderer)
        return json.loads(renderer)

    def get_grid_voltage_level(self, serial: str):
        json = self.fetch(
            f'gen2api/pc/owner/inverter/current_info_plus/{serial}',
            self.token)

        return {
            'grid': {
                'l1': json['body'][2]['contents'][0]['contents'][0]['value'],
                'l2': json['body'][2]['contents'][0]['contents'][1]['value'],
                'l3': json['body'][2]['contents'][0]['contents'][2]['value'],
            }
        }
