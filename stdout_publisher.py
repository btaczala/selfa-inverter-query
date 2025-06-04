import logging


class StdOutPublished:

    def publish(self, json: str):
        logging.info(f'StdoutPublisher: {json}')
