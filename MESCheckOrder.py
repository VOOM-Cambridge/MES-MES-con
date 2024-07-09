
from freppleAPImodule import freppleConnect
import multiprocessing
import logging
import zmq
import json
from datetime import datetime

context = zmq.Context()
logger = logging.getLogger("Check Orders")

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
        self.supplierNameList = [x["name"] for x in self.supplier]
        self.customer = config["mqtt_publish"]["customer"]
        self.customerNameList = [x["name"] for x in self.customer]
        self.addressSupplier ={}
        self.addressCustomer = {}
        for supplier in self.supplierNameList:
            self.addressSupplier[supplier["name"]] = supplier["address"]
        for customer in self.customerNameList:
            self.addressCustomer[customer["name"]] = customer["address"]


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

    def checkPurcahseOrders(self, order):
        # find all purchase orders for new order, send purchase orders and confirm
        outNotConfirmend = self.frepple.findAllPurchaseOrdersOrd(order, "proposed")
        for outOrd in outNotConfirmend:
            logger.info("new order found to process purchases for")
            # send for new order, send messeage with purchase order
            # check if purchase orders have been confirmed if not send a messeage 
            if outOrd["supplier"] in self.supplierNameList: 
                #supplier is one connected to who can be comunciated with
                reciever = outOrd["supplier"]
                try:
                    addressToSend = self.addressSupplier[reciever]
                except:
                    addressToSend = ""

                logger.info("reciever: "  + reciever + " " + addressToSend)
                if "Raw Material" not in reciever and addressToSend != "":
                    # send on the order back up the supply chain or send a reminder
                    msg_payload = self.messageChangeForSupplier(outOrd)
                    logger.info("suppliers")
                    self.zmq_out.send_json({'send to': reciever, 'topic': self.topic, 'payload': msg_payload})
                else:
                    # confirm order is ok set confirmation in purchase automatically (supplier wont do it)
                    logger.info("confirmed becuase not there")
                    outOrd["status"] = "confirmed"
                    self.frepple.purchaseOrderFunc("EDIT", outOrd)
            else:
                # supplier not in list of comunciaiton ones so set to confirmed
                outOrd["status"] = "confirmed"
                self.frepple.purchaseOrderFunc("EDIT", outOrd)

        # update order if confirmed to open
        self.checkOrdersConfirmed(order)

    def checkOrdersConfirmed(self, order):
        # set all order confirmed to complete 
        outNotConfirmend = self.frepple.findAllPurchaseOrdersOrd(order, "proposed")
        if outNotConfirmend == None or not outNotConfirmend:
            
            logger.info("All purchase orders set to confirmed change order to open")
            orderInfo ={}
            orderInfo["name"] = order
            dataBack = self.frepple.ordersIn("GET", orderInfo)
            reciever = dataBack["customer"]
            dataBack["status"] = "open"
            self.frepple.ordersIn("EDIT", dataBack)
            # send update to customer
            logger.info("************  order " + order + " update to open ****************")
            msg_payload = self.messageChangeForCustomer(dataBack)
            
            if reciever in self.customerNameList:    
                try:
                    cusAddressToSend = self.addressCustomer[reciever]
                except:
                    cusAddressToSend = ""
                if cusAddressToSend != "":
                    msg_payload["status"] = "confirmed"
                    topic = "MES/purchase/" + self.name + "/update/"
                    self.zmq_out.send_json({'send to': reciever, 'topic': topic, 'payload': msg_payload})
                else:
                    logger.info("No comunication channel for cusotmer")
            else:
                logger.info("No customer to send to")
        # elif len(outNotConfirmend[0]["plan"]["pegging"]) > 1:
        #     # purchase order assigned to more than one order
        #     oldPurchase = outNotConfirmend[0]

    def checkOrdersStillConfirmed(self, orderIn):
        outNotConfirmend = self.frepple.findAllPurchaseOrdersOrd(orderIn, "proposed")
        if outNotConfirmend:
            # if there are jobs in proposed then need to change order to reflect 
            logger.info("MES Check: Change order to quote")
            payload = {"name": orderIn}
            dataBack = self.frepple.ordersIn("GET", payload)
            if dataBack:
                if dataBack["status"] == "open":
                    dataBack["status"] = "quote"
                    self.frepple.ordersIn("EDIT", dataBack)
        
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
        return newMess
    
    def messageChangeForCustomer(self, orderInfo):
        # reverse of above function
        newMess ={}
        newMess["reference"] =  orderInfo["name"]  
        newMess["item"] = orderInfo["item"] 
        newMess["supplier"] = self.name 
        newMess["quantity"] = orderInfo["quantity"] 
        newMess["enddate"] = orderInfo["due"] 
        newMess["location"] = "Goods In"
        return newMess

        
    def run(self):
        self.do_connect()
        self.frepple = freppleConnect(self.user, self.password, self.url)
        logger.info("Connected")
        run = True
        timeReading = datetime.now()
        while run:
            if (datetime.now() -timeReading).total_seconds()>self.frequency:
                # find all Inquiry orders not confirmed and check
                ordNewQuote = self.frepple.findAllOrders("quote")
                
                for order in ordNewQuote:
                    # place the new orders with other MES software
                    logger.info("checking order " + order + " and sending confirmation")
                    self.checkPurcahseOrders(order)

                ordNew = self.frepple.findAllOrders("open")
                for order in ordNew:
                    self.checkOrdersStillConfirmed(order)
                    
                timeReading = datetime.now()
                logger.info("Run plan .............")
                self.frepple.runPlan()


                    

                # client.loop(0.05)
