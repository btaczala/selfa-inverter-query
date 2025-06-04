import logging


class MqttPublisher:

    def __init__(self, host: str, port: int, topic: str, username: str,
                 password: str):
        self.host = host
        self.port = port
        self.topic = topic
        self.username = username
        self.password = password

    def publish(self, json: str):
        logging.info(f'MqttPublisher: {json}')
