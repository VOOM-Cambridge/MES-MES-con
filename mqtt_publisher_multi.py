import paho.mqtt.client as mqtt
import multiprocessing
import logging
import zmq
import json
from datetime import datetime

context = zmq.Context()
logger = logging.getLogger("MQTT publisher")

class MessagePublisherMulti(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()

        mqtt_conf = config['mqtt_publish']
        self.suppliers = mqtt_conf["supplier"]
        self.customers = mqtt_conf["customer"]
        self.supplierNameList = [x["name"] for x in mqtt_conf["supplier"]]
        self.customerNameList = [x["name"] for x in mqtt_conf["customer"]]

        # Declarations
        self.zmq_conf = zmq_conf
        self.zmq_in = None
        self.supplier_clients = {}
        self.customer_clients = {}

    def do_connect(self):
        self.zmq_in = context.socket(self.zmq_conf['type'])
        if self.zmq_conf["bind"]:
            self.zmq_in.bind(self.zmq_conf["address"])
        else:
            self.zmq_in.connect(self.zmq_conf["address"])

    def mqtt_connect(self, client, config):
        logger.info('connecting to ' + config["address"] + ':' + str(config["port"]))
        client.connect(config["address"], config["port"], 60)
    
    def on_mess(client, userdata, message):
        logger.info("{'" + str(message.payload) + "', " + str(message.topic) + "}")

    def on_disconnect(self, client, _userdata, rc):
        if rc != 0:
            logger.info(f"Unexpected MQTT disconnection (rc:{rc}), reconnecting...")
            for supplier in self.suppliers:
                if supplier["address"] == client._host:
                    self.mqtt_connect(client, supplier)
                    return
            for customer in self.customers:
                if customer["address"] == client._host:
                    self.mqtt_connect(client, customer)
                    return

    def mqtt_connect_call(self):
        for supplier in self.suppliers:
            if supplier["address"]:
                client = mqtt.Client()
                client.on_disconnect = self.on_disconnect
                client.on_message = self.on_mess
                try:
                    self.mqtt_connect(client, supplier)
                    self.supplier_clients[supplier["name"]] = client
                except Exception as e:
                    logger.error(f"Error connecting to supplier {supplier['name']}: {e}")

        for customer in self.customers:
            if customer["address"]:
                client = mqtt.Client()
                client.on_disconnect = self.on_disconnect
                client.on_message = self.on_mess
                try:
                    self.mqtt_connect(client, customer)
                    self.customer_clients[customer["name"]] = client
                except Exception as e:
                    logger.error(f"Error connecting to customer {customer['name']}: {e}")

    def run(self):
        self.do_connect()
        self.mqtt_connect_call()

        timeLast = datetime.now()
        run = True
        while run:
            while self.zmq_in.poll(50, zmq.POLLIN):
                try:
                    msg = self.zmq_in.recv(zmq.NOBLOCK)
                    msg_json = json.loads(msg)
                    msg_topic = msg_json['topic']
                    msg_payload = msg_json['payload']
                    receiver = msg_json["send to"]

                    if receiver in self.supplierNameList:
                        client = self.supplier_clients.get(receiver)
                        if client:
                            logger.info(f"Sending message {msg_payload} to supplier at: {receiver}")
                            msg_topic = msg_topic.replace("purchase", "order")
                            client.publish(topic=msg_topic, payload=json.dumps(msg_payload), qos=1)
                    elif receiver in self.customerNameList:
                        client = self.customer_clients.get(receiver)
                        if client:
                            logger.info(f"Sending message {msg_payload} to customer at: {receiver}")
                            msg_topic = msg_topic.replace("order", "purchase")
                            client.publish(topic=msg_topic, payload=json.dumps(msg_payload), qos=1)
                except zmq.ZMQError:
                    pass

                if (datetime.now() - timeLast).total_seconds() > 120:
                    self.mqtt_connect_call()
                    timeLast = datetime.now()
