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

    supp = conf['mqtt_publish']["supplier"]
    print(supp)
    # frepple = freppleConnect("admin", "admin", "http://129.169.48.173:9000")
    # output = frepple.findAllPurchaseOrdersOrd("EMS100", "proposed")

    # mess = {}
    # mess["reference"] = "2"
    # mess["item"] = "ABS material roll"
    # mess["supplier"] = "ABS material supplier"
    # mess["quantity"] = "94.00000000"
    # mess["enddate"] = "2024-01-11T00:56:51"
    # mess["location"] = "Goods In"
    # mess["status"] = "confirmed"
        
    # outNotConfirmend = frepple.findAllPurchaseOrdersOrd("EMS10000", "proposed")
    # print(outNotConfirmend)
    # x = outNotConfirmend[0]["plan"]["pegging"]
    # out = frepple.purchaseOrderFunc("EDIT", mess)
    # print(out)


