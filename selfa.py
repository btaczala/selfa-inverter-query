import logging
import requests

base_url = 'https://lb.solinteg-cloud.com/'


class Selfa:

    def __init__(self, token):
        self.token = token
        logging.info(f"token is {self.token}")

    # def get_current_info(self):
    #     # Placeholder for the logic to get current info
    #     logging.info("Getting current info...")
    #     return {"info": "This is the current info"}
    #
    def fetch(self, rest_of_url: str, token: str):
        headers = {'token': f'{token}'}
        ret = requests.get(f'{base_url}/{rest_of_url}', headers=headers)

        return ret.json()

    def list(self):
        return self.fetch('gen2api/app/owner/station/myList?searchFilter=',
                          self.token)

    def get_current_info(self, stationId: str):
        return self.fetch(
            f'gen2api/pc/distributor/station/stationCurrentInfo/{stationId}/system?stationId={stationId}',
            self.token)
