
import paho.mqtt.client as mqtt

import multiprocessing
import logging
import zmq
import json
from datetime import datetime
context = zmq.Context()
logger = logging.getLogger("MQTT publisher")

class messeagePublisher(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()

        mqtt_conf = config['mqtt_publish']
        self.supplier = mqtt_conf["supplier"][0]
        self.customer = mqtt_conf["customer"][0]
        self.supplierNameList = [x["name"] for x in mqtt_conf["supplier"]]
        self.customerNameList = [x["name"] for x in mqtt_conf["customer"]]

        # declarations
        self.zmq_conf = zmq_conf
        self.zmq_in = None

    def do_connect(self):
        self.zmq_in = context.socket(self.zmq_conf['type'])
        if self.zmq_conf["bind"]:
            self.zmq_in.bind(self.zmq_conf["address"])
        else:
            self.zmq_in.connect(self.zmq_conf["address"])

    def mqtt_connect(self, client, config):
        logger.info('connecting to '+ config["address"] + ':' + str(config["port"]))
        connect_future = client.connect(config["address"], config["port"], 60)
        #connect_future.result()  # will raise error on failure

    def on_mess(client, userdata, message):
        logger.info("{'" + str(message.payload) + "', " + str(message.topic) + "}")

    def on_connection_interrupted(self, connection, error, **kwargs):
        logger.info("Connection interrupted. error: {}".format(error))

    # Callback when an interrupted connection is re-established.
    def on_connection_resumed(self, connection, return_code, session_present, **kwargs):
        logger.info("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

        if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
            logger.warning("Session did not persist. Resubscribing to existing topics...")
            resubscribe_future, _ = connection.resubscribe_existing_topics()

            # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
            # evaluate result with a callback instead.
            resubscribe_future.add_done_callback(self.on_resubscribe_complete)

    def on_resubscribe_complete(self, resubscribe_future):
        resubscribe_results = resubscribe_future.result()
        logger.info("Resubscribe results: {}".format(resubscribe_results))

        for topic, qos in resubscribe_results['topics']:
            if qos is None:
                logger.info("Server rejected resubscribe to topic: {}".format(topic))

    def on_disconnect(self, client, _userdata, rc):
        if rc != 0:
            logger.info(f"Unexpected MQTT disconnection (rc:{rc}), reconnecting...")
            if self.supplier["address"] !="":
                clientSupply = mqtt.Client()
                self.mqtt_connect(clientSupply, self.supplier)
                clientSupply.on_publish = self.on_mess()
        
            if self.customer["address"] !="":
                clientCustomer = mqtt.Client()
                self.mqtt_connect(clientCustomer, self.customer)
                clientCustomer.on_publish = self.on_mess()

    def mqtt_connect_call(self):
        if self.supplier["address"] !="":
            self.clientSupply = mqtt.Client()
            #self.mqtt_connect(self.clientSupply, self.supplier)
            try:
                self.mqtt_connect(self.clientSupply, self.supplier)
            except:
                print("Error connecteing Supplier")
        
        if self.customer["address"] !="":
            self.clientCustomer = mqtt.Client()
            #self.mqtt_connect(self.clientCustomer, self.customer)
            try:
                self.mqtt_connect(self.clientCustomer, self.customer)
            except:
                print("Error connecting Cusotmer")

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
                    reciever = msg_json["send to"]
                    self.mqtt_connect_call()
                    logger.debug(f'pub topic:{msg_topic} msg:{msg_payload}')
                    if reciever in self.supplierNameList and self.supplier["address"] !="":
                        logger.info("sending messeage" + str(msg_payload) + "to supplier at: " + self.supplier["address"])
                        msg_topic.replace("purchase", "order")
                        #msg_topic = reciever + "/" + msg_topic
                        self.clientSupply.publish(topic=msg_topic, payload=json.dumps(msg_payload),qos=1)
                    elif reciever in self.customerNameList and self.customer["address"] !="":
                        logger.info("sending messeage" + str(msg_payload) + "to customer at: " + self.customer["address"])
                        msg_topic.replace("order", "purchase")
                        #msg_topic = reciever + "/" + msg_topic
                        self.clientCustomer.publish(topic=msg_topic, payload=json.dumps(msg_payload),qos=1)
                except zmq.ZMQError:
                    pass

                if (datetime.now() -timeLast).total_seconds()>60:
                    self.mqtt_connect_call()
                    timeLast = datetime.now()


                    

                
            # client.loop(0.05)
