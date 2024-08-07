import multiprocessing
import zmq
import logging
import json
from enum import Enum, auto
import freppleAPImodule
import time

context = zmq.Context()
logger = logging.getLogger("Message Processing")


class MessageProcessing(multiprocessing.Process):
    def __init__(self, config, zmq_conf):
        super().__init__()

        conf = config["frepple_info"]
        self.url = conf['URL']
        self.user = conf["user"]
        self.password = conf["password"]
        self.name = config["Factory"]["name"]

        # declarations
        self.zmq_conf = zmq_conf
        self.zmq_in = None
        self.zmq_out = None

    def do_connect(self):
        self.zmq_in = context.socket(self.zmq_conf['in']['type'])
        if self.zmq_conf['in']["bind"]:
            self.zmq_in.bind(self.zmq_conf['in']["address"])
        else:
            self.zmq_in.connect(self.zmq_conf['in']["address"])

        self.zmq_out = context.socket(self.zmq_conf['out']['type'])
        if self.zmq_conf['out']["bind"]:
            self.zmq_out.bind(self.zmq_conf['out']["address"])
        else:
            self.zmq_out.connect(self.zmq_conf['out']["address"])

    def run(self):
        logger.info("Starting")
        self.do_connect()
        logger.info("ZMQ Connected")
        self.frepple = freppleAPImodule.freppleConnect(self.user, self.password, self.url)
        run = True
        while run:
            while self.zmq_in.poll(500, zmq.POLLIN):
                msg = self.zmq_in.recv()
                msg_json = json.loads(msg)
                logger.info("MQTT_processing: mess recieved to process")
                breakUp = msg_json['topic'].replace("MES/", "").split("/")
                logger.info(breakUp)
                logger.info(msg_json['payload'])
                reason = breakUp[2]
                partner = breakUp[1]
                if breakUp[0] == "purchase":
                    logger.info("MQTT_processing: purchase update")
                    self.processPurchase(reason, partner, msg_json['payload'])
                elif breakUp[0] == "order":
                    logger.info("MQTT_processing: new or update order")
                    logger.info(reason)
                    logger.info(partner)
                    self.processOrder(reason, partner, msg_json['payload'])
                    
                
    
    def processOrder(self, reason, customer, payload):
        if reason == "update":
            # update orders or job first search for order 
            orders = self.frepple.findAllOrders("open")
            descrip = self.checkDescrip(payload)
            if payload["name"] in orders or descrip in orders:
                # order already exists and cna be updated
                self.frepple.ordersIn("EDIT", payload)
                logger.info("MQTT_processing: order updated")
                self.runUpdates()
            # elif reason == "confirm":
            #     self.frepple.ordersIn("EDIT", payload)
            #     self.runUpdates()   
            else:
                reason == "new"
        elif reason == "infomation":
            logger.info("MQTT_processing: update requested on order status resending info")
            self.resendInfo(payload["name"], customer)
        if reason == "new":
            # create a new order in the MES
            outputCheck = self.frepple.ordersIn("GET", payload)
            logger.info("OOOOOOOOOOOOO    check is it exisits  ooooooooooooo")
            logger.info(outputCheck)
            if not outputCheck or outputCheck == None or outputCheck == []:
                logger.info("MQTT_processing: started new addition")
                output = self.frepple.ordersIn("ADD", payload)
                logger.info(output)
                logger.info("MQTT_processing: new added")
                time.sleep(10)
                self.runUpdates()
            else:
                #self.checkNotAlreadyDone(outputCheck, customer)
                logger.info("Order already exists ask for refresh")
                if outputCheck["status"] == "open":
                    msg_payload = self.messageChangeForCustomer(outputCheck)
                    msg_payload["status"] = "confirmed"
                    topic = "MES/purchase/" + self.name + "/update/"
                    self.zmq_out.send_json({'send to': customer, 'topic': topic, 'payload': msg_payload})
                    logger.info("order compleated and confirmed, resending confirmation")


    def checkNotAlreadyDone(self, outputOrder, customer):
        # set all order confirmed to complete 
        outNotConfirmend = self.frepple.ordersIn(outputOrder["name"])
        if outNotConfirmend == None or not outNotConfirmend:
            logger.info("All purchase orders set to confirmed change order to open")
            msg_payload = self.messageChangeForCustomer(outputOrder)
            msg_payload["status"] = "confirmed"
            topic = "MES/purchase/" + self.name + "/update/"
            self.zmq_out.send_json({'send to': customer, 'topic': topic, 'payload': msg_payload})
            logger.info("order compleated and confirmed, resending confirmation")

    def checkDescrip(self, payload):
        try:
            return payload["description"]
        except:
            return "unkown description text"
    
    def checkName(self, payload):
        try:
            return payload["name"]
        except:
            return payload["reference"]

    def processPurchase(self, reason, supplier, payload):
        if reason == "update":
            # update orders or job first search for order 
            logger.info(payload["reference"])
            purchases = self.frepple.findAllPurchaseOrders("confirmed")
            descrip = self.checkDescrip(payload)
            nam = self.checkName(payload)

            if nam in purchases or descrip in purchases:
                # purchse already exists and confiremd and can be updated
                self.frepple.purchaseOrderFunc("EDIT", payload)
                logger.info("purchase updated from confirmed")
                self.runUpdates()

            purchases = self.frepple.findAllPurchaseOrders("proposed")  + self.frepple.findAllPurchaseOrders("approved")
            nam = self.checkName(payload)
            if nam in purchases or descrip in purchases:
                # purchase already exists and not confirmed yet and can be upadtes
                self.frepple.purchaseOrderFunc("EDIT", payload)
                logger.info("MQTT_processing: purchase updated from proposed")
                self.runUpdates()
        elif reason == "confirm":
            self.frepple.purchaseOrderFunc("EDIT", payload)
            self.runUpdates()
    
    def resendInfo(self, order, customer):

        info = self.frepple.ordersIn("GET", order)
        if info and info !=[]:
            payload = self.messageChangeForCustomer(info)
            topic = "MES/purchase/"+ self.name +"/update/"

            try:
                self.zmq_out.send_json({'send to': customer, 'topic': topic, 'payload': payload})
            except zmq.ZMQError:
                logger.info("MQTT_processing: Error sending messeage on")
                pass

    def runUpdates(self):
        # collect all order information before on delivery data and status
        try:
            with open('./data/orders.json', 'r') as f:
                startOrderData = json.load(f)
        except:
            startOrderData = self.frepple.findAllOrdersExtraInfo("open", ["name", "deliverydate", "status"])
        self.frepple.runPlan()
        time.sleep(2)
        endOrderData = self.frepple.findAllOrdersExtraInfo("open", ["name", "deliverydate", "status"])
        dateToUpdate =[]
        for data in endOrderData:
            if data not in startOrderData:
                if data[0] in startOrderData:
                    # end date of order has changed but the order is still there
                    dateToUpdate.append(data)
                elif data[0] not in startOrderData:
                    # new order
                    dateToUpdate.append(data)
        logger.info("++++++++++ Data to update +++++++++")
        logger.info(dateToUpdate)
        for data in dateToUpdate:
            # get new data for order send out data
            info = self.frepple.ordersIn("GET", {"name": data[0]})
            if info != [] or info != None:
            # send on messeage to cusotmer of that order - only customer needs updating others detemined by supplier
                payload = self.messageChangeForCustomer(info)
                topic = "MES/purchase/"+ self.name +"/update/"
                keys_list = ["item", "quantity"]
                try:
                    self.zmq_out.send_json({'send to': info["customer"], 'topic': topic, 'payload': payload})
                except zmq.ZMQError:
                    logger.info("MQTT_processing: Error sending messeage on")
                    pass
        with open('./data/orders.json', 'w') as f:
            json.dump(endOrderData, f)
    
    def messageChangeForSupplier(self, orderInfo):
        newMess ={}
        newMess["name"] =  orderInfo["reference"] # order number from purchase order number 
        newMess["item"] = orderInfo["item"] # what is being ordered 
        newMess["customer"] = self.name # name of current factory 
        newMess["quantity"] = orderInfo["quantity"] # quantity needed in purchase order
        newMess["due"] = orderInfo["enddate"]
        newMess["location"] = "Goods Out"
        try: 
            newMess["description"] = str(orderInfo["plan"]["pegging"]) # any other details needed
        except:
            pass
    
    def messageChangeForCustomer(self, orderInfo):
        # reverse of above function
        newMess ={}
        newMess["reference"] =  orderInfo["name"]  
        newMess["item"] = orderInfo["item"] 
        newMess["supplier"] = self.name 
        newMess["quantity"] = orderInfo["plannedquantity"] 
        newMess["enddate"] = orderInfo["deliverydate"]
        #newMess["priority"] = orderInfo["priority"] 
        newMess["location"] = "Goods In"
        return newMess
    
                    
        