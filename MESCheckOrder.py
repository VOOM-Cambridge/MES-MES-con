
from freppleAPImodule import freppleConnect
import multiprocessing
import logging
import zmq
import json
from datetime import datetime

context = zmq.Context()

class FreppleCheckerOrders(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()

        conf = config["frepple_info"]
        self.url = conf['URL']
        self.user = conf["user"]
        self.password = conf["password"]
        self.name = config["Factory"]["name"]
        self.topic = "MES/order/" + config["Factory"]["name"] +"/new/"
        self.frequency = config["Factory"]["frequencyCheck"]
        self.supplierAddress = config["mqtt_publish"]["supplier"]

        # declarations
        self.zmq_conf = zmq_conf
        self.zmq_out = None
        self.zmq_out_intenral =None

    def do_connect(self):
        self.zmq_out = context.socket(self.zmq_conf["out"]['type'])
        if self.zmq_conf["out"]["bind"]:
            self.zmq_out.bind(self.zmq_conf["out"]["address"])
        else:
            self.zmq_out.connect(self.zmq_conf["out"]["address"])
        
        self.zmq_out_internal = context.socket(self.zmq_conf["internal"]['type'])
        if self.zmq_conf["internal"]["bind"]:
            self.zmq_out_internal.bind(self.zmq_conf["internal"]["address"])
        else:
            self.zmq_out_internal.connect(self.zmq_conf["internal"]["address"])

    def newOrderAdded(self, order):
        # find all purchase orders for new order, send purchase orders and confirm
        outConfirmed = self.frepple.findAllPurchaseOrdersOrd(order, "confirmed")
        outNotConfirmend = self.frepple.findAllPurchaseOrdersOrd(order, "proposed")
        for outOrd in outNotConfirmend:
            print("new order foud to process")
            # send for new order, send messeage with purchase order
            msg_payload = self.messageChange(outOrd)
            reciever = outOrd["supplier"]
            if "Raw Material" not in reciever or self.supplierAddress == "":
                self.zmq_out.send_json({'send to': reciever, 'topic': self.topic, 'payload': msg_payload})
            else:
                # confirm order is ok set confirmation
                msg_payload["status"] = "confirmed"
                self.frepple.purchaseOrderFunc("EDIT", msg_payload)
                topic = self.topic.replace("new", "update") # change topic to update not new
                self.zmq_out_internal.send_json({'topic': self.topic, 'payload': msg_payload})

    def messageChange(self, orderInfo):
        newMess ={}
        newMess["name"] =  orderInfo["reference"] # order number from purchase order number 
        newMess["item"] = orderInfo["item"] # what is being ordered 
        newMess["customer"] = self.name # name of current factory 
        newMess["quantity"] = orderInfo["quantity"] # quantity needed in purchase order
        newMess["description"] = "" # any other details needed
        newMess["due"] = orderInfo["enddate"]
        newMess["priority"] = 1 # default is 1
        newMess["location"] = "Goods Out"
        return newMess

        
    def run(self):
        self.do_connect()
        self.frepple = freppleConnect(self.user, self.password, self.url)
        print("Connected")
        ordOld =[]
        run = True
        timeReading = datetime.now()
        while run:
            if (datetime.now() -timeReading).total_seconds()>self.frequency:
                ordIn = self.frepple.findAllOrders("open")
                s = set(ordOld)
                temp = [x for x in ordIn if x not in s]
                ordOld = ordIn
                timeReading = datetime.now()
                for order in temp:
                    # place the new orders with other MES software
                    self.newOrderAdded(order)


                # client.loop(0.05)
