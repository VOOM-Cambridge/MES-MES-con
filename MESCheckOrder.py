
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
        self.supplier = config["mqtt_publish"]["supplier"]
        self.supplier = config["mqtt_publish"]["customer"]


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

    def newOrderToCheck(self, order):
        # find all purchase orders for new order, send purchase orders and confirm
        outNotConfirmend = self.frepple.findAllPurchaseOrdersOrd(order, "proposed")
        supplierCompleted = True
        for outOrd in outNotConfirmend:
            print("new order found to process")
            # send for new order, send messeage with purchase order
            # check if purchase orders have been confirmed if not send a messeage 
            for suppliers in self.supplier:
                if suppliers["name"] == outOrd["supplier"]: 
                    #supplier is one connected to who can be comunciated with
                    supplierCompleted = False
                    reciever = outOrd["supplier"]
                    print(reciever)
                    msg_payload = self.messageChange(outOrd)
                    if "Raw Material" not in reciever or self.supplier["address"] != "":
                        # send on the order back up the supply chain
                        self.zmq_out.send_json({'send to': reciever, 'topic': self.topic, 'payload': msg_payload})
                    else:
                        # confirm order is ok set confirmation in purchase automatically (supplier wont do it)
                        msg_payload["status"] = "confirmed"
                        self.frepple.purchaseOrderFunc("EDIT", msg_payload)
            
            if supplierCompleted:
                self.upadteToConfirmedAndOpen(order)


    def upadteToConfirmedAndOpen(self, order):
        # set all order confirmed to complete 
        outNotConfirmend = self.frepple.findAllPurchaseOrdersOrd(order, "proposed")
        for ord in outNotConfirmend:
            try:
                ord["status"] = "confirmed"
                self.frepple.purchaseOrderFunc("EDIT", msg_payload)
            except Exception as error:
                print(error)
            orderInfo ={}
            orderInfo["name"] = order
            orderInfo["status"] = "open"
            # update order status 
            self.frepple.ordersIn("EDIT", orderInfo)
            dataBack = self.frepple.ordersIn("GET", orderInfo)
            print("****")
            print(dataBack)
            # send on confirmation 
            if dataBack != None:
                topicOut = self.topic.replace("new", "update")
                try:
                    self.zmq_out.send_json({'send to': dataBack["customer"], 'topic': topicOut, 'payload': dataBack})
                except zmq.ZMQError:
                    pass

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
        run = True
        timeReading = datetime.now()
        while run:
            if (datetime.now() -timeReading).total_seconds()>self.frequency:
                # find all Inquiry orders not confirmed and check
                ordNewQuote = self.frepple.findAllOrders("quote")
                timeReading = datetime.now()
                for order in ordNewQuote:
                    # place the new orders with other MES software
                    self.newOrderToCheck(order)

                # client.loop(0.05)
