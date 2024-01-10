import requests
from base64 import b64encode
import json
from datetime import datetime

class freppleConnect:
    def __init__(self, user, passw, URL):
        self.BASE_URL = URL #"http://localhost:9000"
        self.username = user
        self.password = passw
        self.payload = {}
        self.headers = {
        'Authorization': self.basic_auth(),
        'Content-Type': 'application/json'
        }

    # Basic set up code 
    def basic_auth(self):
        token = b64encode(f"{self.username}:{self.password}".encode('utf-8')).decode("ascii")
        return f'Basic {token}'
    
    def findDataFromResults(self, returnData, first_key, data, keyList, ind):
        dataToReturn = []
        if first_key in data and data[first_key] != "":
            for itemsData in returnData:
                if itemsData[first_key] == data[first_key]:
                    dataToReturn.append(itemsData)
            if len(dataToReturn)==1:
                return dataToReturn[0]
            elif len(dataToReturn)>1:
                if len(keyList)>ind+2:
                    first_key = keyList[ind+1]
                    return self.findDataFromResults(dataToReturn, first_key, data, keyList, ind+1)                    
                else:
                    return None

    def findDataFromResultsMulti(self, returnData, first_key, data):
        dataToReturn = []
        if data[first_key] != "":
            for itemsData in returnData:
                if first_key in data:
                    if itemsData[first_key] == data[first_key]:
                        dataToReturn.append(itemsData)
            return dataToReturn
        else: 
            return returnData
            
                
    def runProcess(self, process, payload, data, url):
        first_key = list(payload.keys())[0]
        keyList = list(payload.keys())
        if process == "EDIT":
            response = requests.request("GET", url, headers=self.headers, data=data)
            if response.status_code == 200:
                returnData = response.json()
                payload = self.findDataFromResults(returnData, first_key, data, keyList, 0)
                
        payload.update(data)
        try:
            set_key = list(data.keys())[0]
        except:
            set_key = first_key

        dic = payload
        payload = json.dumps(dic)
        match process:
            case "GET":
                pros = "GET"
                payload = payload
            case "GETALL":
                pros = "GET"
                payload = payload
            case "ADD":
                pros = "POST"
            case "REMOVE":
                pros = "DELETE"
                url = url + str(data[first_key]).replace(" ", "%20") + "/"
            case "EDIT":
                pros = "POST"
            case default:
                pros = "GET"
                payload = None
        response = requests.request(pros, url, headers=self.headers, data=payload)
        if response.status_code == 200:
            responseData = response.json()
            if process == "GETALL":
                searchData = self.findDataFromResultsMulti(responseData, set_key, data)
                
            else:
                searchData = self.findDataFromResults(responseData, first_key, data, keyList, 0)       

            if searchData ==None:
                return responseData
            else:
                return searchData
        elif response.status_code == 201:
            print("New data added succefully")
            return None
        elif response.status_code == 204:
            print(str(data[first_key]) + " deleted from database.")
            return None
        else:
            print('Get data failed:')
            print(response.status_code)
            return None
        
    # Function to change orders 
    def ordersIn(self, process, data):
        url = self.BASE_URL + "/api/input/demand/"
        payload =     {
            "name": "",
            "item": "",
            "location": "",
            "customer": "",
            "due": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            "quantity": "0",
            "priority": "100",
            } # some default values are added to prevent errors
        
        # if new order in to add make default addition as quote
        if process == "ADD":
            payload["status"] = "quote"
        
        return self.runProcess(process, payload, data, url)

    # Function to change items 
    def itemsFunc(self, process, data):
        url = self.BASE_URL + "/api/input/item/"
        payload =     {
            "name": "",
            "owner": "All items",
            "description": ""
            }
        return self.runProcess(process, payload, data, url)

    # Function to re-run planning algorithm
    def runPlan(self):
        url = self.BASE_URL + "/execute/api/runplan/?constraint=13&plantype=1&env=fcst,supply"
        response = requests.request("POST", url, headers=self.headers, data=self.payload)
        if response.status_code == 200:
            return response.json()
        else:
            print('Get data failed:' + response.status_code)
            return None

    # Function to see all factroy locations 
    # get all factory locations
    def locationFunc(self, process, data):
        url = self.BASE_URL + "/api/input/location/"
        payload =     {
            "name": "",
            "owner": "All locations"
            }
        return self.runProcess(process, payload, data, url)

    # Function to look for or edit purchase orders 
    # get all orders open, get all orders closed, add delay/change time arrival to set order, add new barcode or reference to order, change order status,
    def purchaseOrderFunc(self, process, data):
        url = self.BASE_URL + "/api/input/purchaseorder/"
        payload =     {
                "reference": "",
                "quantity": "",
                "item": None,
                "supplier": None,
                # "startdate": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                # "enddate": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                "location": None,
                }
        if process == "ADD" and "item" in data:
            #find supplier details
            itemD = data["item"]
            supplierData = self.supplierFunc("GET", {"item": itemD})
            payload["supplier"] = supplierData["supplier"]
            payload["location"] = supplierData["location"]

        return self.runProcess(process, payload, data, url)

    # Function to add or edit cusotmers 
    # get all cusotmers, add or remove cusotmer 
    def customerFunc(self, process, data):
        url = self.BASE_URL + "/api/input/customer/"
        payload =     {
            "name": "",
            "owner": "All customers"
            }
        return self.runProcess(process, payload, data, url)

    # Function to add/edit supplier/item supplier or edit exisitng one (including chnaging leadtime)
    # get all supplier, edit supplier (lead time, name, cost), edit item supplier (lead time, name, cost), 
    def supplierFunc(self, process, data):
        # data should have name and item or itemsupplir change details
        url = self.BASE_URL + "/api/input/supplier/"
        url2 = self.BASE_URL + "/api/input/itemsupplier/"
        payload = {"item": "", 
                "supplier": "",
                "location": "Goods In Warehouse",
                "leadtime": "1 00:00:00",
                "sizeminimum": 1}
        #if process is GET then fetch infomation for item supplier (assume they want supplier of item)
        if process == "GET":
            payload = {"item": ""}
            if "item" in data:
                payload["item"] = data["item"]
            # data["item"] = data["item"]
            # data.pop("name") 
            return self.runProcess(process, payload, data, url2)
        elif process == "ADD": #if process is add new supplier also add item supplier
            # check if existing supplier
            datanew ={}
            if "supplier" in data:
                datanew["name"] = data["supplier"]
            elif "name" in data:
                datanew["name"] = data["name"]
            else:
                datanew["name"] = ""
            #check if exisitng supplier with that name
            response = self.runProcess("GET", datanew, datanew, url)
            print("checked and: " + str(response))
            payload["supplier"] = datanew["name"]
            if response == None:
                # no exisitng supplier create one and item supplier and supplier
                self.runProcess("ADD", datanew, datanew, url)
                data["supplier"] = datanew["name"]
                return self.runProcess("ADD",payload, data, url2)
            else:
                # exisitng supplier so create new item supplier linked to that
                data["supplier"] = datanew["name"]
                return self.runProcess("ADD",payload, data, url2)
        elif process == "EDIT":
            # assume item supplier mostly edited
            return self.runProcess("EDIT",data, data, url2)
        elif process == "REMOVE":
            # can only remove item supplier not supplier fully, but supplier can sit on database without being in the way
            results = self.runProcess("GET", payload, {}, url2)
            first_key = list(payload.keys())[0]
            keyList = list(payload.keys())
            output = self.findDataFromResults(results, first_key, data, keyList, 0)
            if not output:
                print("Data not found")
            else:
                return self.runProcess("REMOVE",output, output, url2)

    # Function to edit or get inventory details 
    # get all details of inventory avaible now, see inventory predicted for futrue
    # def inventoryFunc(self, process, data):
    #     url = self.BASE_URL + "/api/input/customer/"
    #     payload =     {
    #         "name": "",
    #         "owner": "All customers"
    #         }
    #     return self.runProcess(process, payload, data, url)

    # Function to edit or get inventory buffers needed
    # get all buffers currently, edit of change set buffer in inventory


    # Function to get manufacturing operation data out to new app view/database 
    # get all manufacturing operations in list (name, date start, date end, quantity, parts to make, order number/name), change/delay an operation
    def manufactOrder(self, process, data):
        url = self.BASE_URL + "/api/input/manufacturingorder/"
        payload = {
                "reference": "",
                "description": "",
                "operation": None,
                "quantity": None,
                "status": None,
                "quantity_completed": None,
                "startdate": None,
                "enddate": None
                }
        return self.runProcess(process,payload, data, url)
    # Fucntion to remove machine from operation (all machines must have calendar with "<machine name> working hours")

    def operation(self, process, data):
        url = self.BASE_URL + "/api/input/operation/"
        payload = {
            "name": "",
            "item": "",
            "type": "time_per",
            "location": "",
            "duration": "00:00:01",
            "duration_per": "00:00:01"
        }
        return self.runProcess(process, payload, data, url)
    
    
    def operationMaterials(self, process, data):
        url = self.BASE_URL + "/api/input/operationmaterial/"
        payload = {
            "operation": "",
            "item": "",
            "quantity": ""
        }
        return self.runProcess(process, payload, data, url)
    
    # Function to change resources 
    def resourceFunc(self, process, data):
        url = self.BASE_URL + "/api/input/resource/"
        payload =     {
            "name": ""
            }
        return self.runProcess(process, payload, data, url)

    def findList(self, data, key):
        items =[]
        for ite in data:
            if ite[key] not in items:
                items.append(ite[key])
        return items
    
    def findMultiList(self, data, keys):
        items =[]
        for ite in data:
            newItem = []
            for key in keys:
                newItem.append(ite[key])
            items.append(newItem)
        return items
    
    def findMultiListLevel(self, data, secHeading, toFind):
        items =[]
        for ite in data:
            sectionToSearch = ite
            for key in secHeading:
                sectionToSearch = sectionToSearch[key]
            if toFind in sectionToSearch:
                items.append(ite)
        return items

    # function to return list of only data from json you want (e.g. names of items, times of deliviery)
    def findAllItems(self):
        data = self.itemsFunc("GET", {})
        return self.findList(data, "name")
    
    # function to return all order numbers
    def findAllOrders(self, status):
        data = self.ordersIn("GETALL", {"status":status})
        return self.findList(data, "name")
    
    def findAllOrdersExtraInfo(self, status, keys):
        data = self.ordersIn("GETALL", {"status":status})
        return self.findMultiList(data, keys)
    
    def findAllPurchaseOrdersOrd(self, orderNumber, status):
        sectionHeading = ["plan", "pegging"]
        data = self.purchaseOrderFunc("GETALL", {"status": status})
        #print(data)
        return self.findMultiListLevel(data, sectionHeading, orderNumber) 
    
    def findAllPurchaseOrders(self, status):
        data = self.purchaseOrderFunc("GETALL", {"status": status})
        return self.findMultiList(data, "reference")

    def findAllCustomers(self):
        data = self.customerFunc("GET", {})
        return self.findList(data, "name")
    
    def findAllLocations(self):
        data = self.locationFunc("GET", {})
        return self.findList(data, "name")
    
    def findAllManOr(self, status):
        data = self.manufactOrder("GETALL", {"status":status})
        return self.findList(data, "name")
    
    def findAllManOpExtraInfo(self, status, keys):
        data = self.manufactOrder("GETALL", {"status":status})
        return self.findMultiList(data, keys)
    
    def findAllManOpByOrders(self, order_num):
        orders = self.manufactOrder("GET", {})
        orderNum = self.findAllManOp("open")
        output =[]
        for order in orders:
            dataFrom = order["plan"]["pegging"]
            if order_num in dataFrom:
                # format [ man. op. number, operation, quantity]
                output.append([order["reference"], order["operation"], dataFrom[order_num]]) 
        return output
    
    def findAllPartsMaterials(self, item):
        data = self.operation("GETALL", {"item": item})
        if data != [] or data != None:
            data = data[0]
            opp = self.operationMaterials("GETALL", {"operation": data["name"]})
            info = []
            for opperation in opp:
                quantity = float(opperation["quantity"])
                if quantity < 0: # material goes into product
                    info.append([opperation["item"], quantity])
            
            return info
        else:
            return None
        



