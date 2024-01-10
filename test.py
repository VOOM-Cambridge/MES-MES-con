import tomli
import time
import logging
import zmq
# local
import MESCheckOrder
import mqtt_pubished
import mqtt_messeage_processing
import mqtt_subscriber
from freppleAPImodule import freppleConnect
import multiprocessing

def get_config():
    with open("./config/config.toml", "rb") as f:
        toml_conf = tomli.load(f)
    return toml_conf

if __name__ == "__main__":
    conf = get_config()

    frepple = freppleConnect("admin", "admin", "http://129.169.48.175:9000")
    output = frepple.findAllPurchaseOrdersOrd("EMS100", "proposed")

    outNotConfirmend = frepple.findAllPurchaseOrdersOrd("EMS10000", "proposed")
    print(outNotConfirmend)
    x = outNotConfirmend[0]["plan"]["pegging"]
    print(len(x))


