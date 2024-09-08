# Check config file is valid
# create BBs
# plumb BBs together
# start BBs
# monitor tasks

# packages
import tomli
import time
import logging
import zmq
# local
import MESCheckOrder
#import mqtt_pubished
import mqtt_publisher_multi
import mqtt_messeage_processing
import mqtt_subscriber

logger = logging.getLogger("main")
logging.basicConfig(level=logging.DEBUG)  # move to log config file using python functionality

def get_config():
    with open("./config/config_man.toml", "rb") as f:
        toml_conf = tomli.load(f)
    logger.info(f"config:{toml_conf}")
    return toml_conf


def config_valid(config):
    return True


def create_building_blocks(config):
    bbs = {}

    mqtt_out_forward = {"type": zmq.PUSH, "address": "tcp://127.0.0.1:4000", "bind": False}
    MESCheckOut = {"type": zmq.PUSH, "address": "tcp://127.0.0.1:4001", "bind": False}
    MESIncomingProcIn = {"type": zmq.PULL, "address": "tcp://127.0.0.1:4000", "bind": True}
    MESIncomingProcOut = {"type": zmq.PUSH, "address": "tcp://127.0.0.1:4001", "bind": False}
    publish_mqtt = {"type": zmq.PULL, "address": "tcp://127.0.0.1:4001", "bind": True}

    bbs["mqtt_subscriber"] = mqtt_subscriber.MQTTSubscriber(config, mqtt_out_forward)
    bbs["MES_order_check"] = MESCheckOrder.FreppleCheckerOrders(config, {'internal': MESIncomingProcOut, 'out': MESCheckOut})
    bbs["process_incoming"] = mqtt_messeage_processing.MessageProcessing(config, {'in': MESIncomingProcIn, 'out': MESIncomingProcOut})
    #bbs["mqtt_publish"] = mqtt_pubished.messeagePublisher(config, publish_mqtt)
    bbs["mqtt_publisher_multi"] = mqtt_publisher_multi.MessagePublisherMulti(config, publish_mqtt)
    return bbs


def start_building_blocks(bbs):
    for key in bbs:
        p = bbs[key].start()


def monitor_building_blocks(bbs):
    while True:
        time.sleep(1)
        for key in bbs:
            # logger.debug(f"{bbs[key].exitcode}, {bbs[key].is_alive()}")
            # todo actually monitor
            pass

if __name__ == "__main__":
    conf = get_config()
    # todo set logging level from config file
    if config_valid(conf):
        bbs = create_building_blocks(conf)
        start_building_blocks(bbs)
        monitor_building_blocks(bbs)
    else:
        raise Exception("bad config")
