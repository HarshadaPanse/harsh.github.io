import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uvicorn import Config, Server
import websockets
import logging
from datetime import datetime, timezone, timedelta
from ocpp.routing import on
from ocpp.v201 import ChargePoint as cp, call_result, call
import ssl
from typing import List, Dict, Any
from fastapi.staticfiles import StaticFiles
import json

logging.basicConfig(level=logging.INFO, # INFO, ERROR, WARNING, DEBUG
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

class ChargePoint(cp):
    def __init__(self, id, connection, central_system):
        super().__init__(id, connection)
        self._central_system = central_system
        self.serial_number = None
        self.model = None
        self.vendor_name = None
        self.firmware_version = None
        self.boot_reason = None
        self.timestamp = None
        self.connectorStatus = None # Available, Occupied, Reserved, Unavailable, Faulted
        self.evse_id = None
        self.connector_id = None

    @on("BootNotification")
    async def on_boot_notification(self, charging_station, reason):
        logging.debug(f"BootNotification charging_station: {charging_station}")
        logging.debug(f"BootNotification reason: {reason}")

        self.serial_number = charging_station.get("serial_number")
        self.model = charging_station.get("model")
        self.vendor_name = charging_station.get("vendor_name")
        self.firmware_version = charging_station.get("firmware_version")
        self.boot_reason = reason

        self._central_system.update_charger_data(self.id, {
            "serial_number": self.serial_number,
            "model": self.model,
            "vendor_name": self.vendor_name,
            "firmware_version": self.firmware_version,
            "boot_reason": self.boot_reason
        })

        result = call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(), interval=10, status="Accepted"
        )
        return result

    @on("Heartbeat")
    def on_heartbeat(self):
        logging.debug("Got a Heartbeat!")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )

    @on("Authorize")
    def on_authorize(*args, **kwargs):
        logging.debug(f"Authorize kwargs: {kwargs}")
        return call_result.AuthorizePayload(
            id_token_info={
               'status':"Accepted",
               'cacheExpiryDateTime':datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
               'chargingPriority':1,
               'language1':"English",
               'language2':"VN",
               'evseId':[123, 456, 789],
               'groupIdToken':
               {
                  'idToken':"Pass1234",
                  'type':"eMAID",
                  'additionalInfo':
                  [
                     {
                        'additionalIdToken':"abc123xyz",
                        'type':"123abc"
                     },
                     {
                        'additionalIdToken':"0abc123xyz",
                        'type':"0123abc"
                     },
                     {
                        'additionalIdToken':"1abc123xyz",
                        'type':"a123abc"
                     }
                  ]
               },
               'personalMessage':
               {
                  'format':"UTF8",
                  'language':"English",
                  'content':"Final total cost of this transaction, including taxes"
               }
            },
            certificate_status="Accepted"
        )

    @on("StatusNotification")
    def on_status_notification(self, **kwargs):
        logging.debug(f"StatusNotification kwargs: {kwargs}")

        self.timestamp = kwargs.get("timestamp")
        self.connectorStatus = kwargs.get('connector_status', self.connectorStatus)
        self.evse_id = kwargs.get("evse_id")
        self.connector_id = kwargs.get("connector_id")

        self._central_system.update_charger_data(self.id, {
            "timestamp": self.timestamp,
            "connectorStatus": self.connectorStatus,
            "evse_id": self.evse_id,
            "connector_id": self.connector_id
        })

        return call_result.StatusNotificationPayload()

    @on("TransactionEvent")
    async def on_transaction_event(self, *args, **kwargs):
        logging.debug(f"TransactionEvent kwargs: {kwargs}")

        transaction_info = kwargs.get("transaction_info", {})
        evse = kwargs.get("evse", {})
        meter_values = kwargs.get("meter_value", [])

        transaction_data = {
            "voltage": None,
            "current": None,
            "frequency": None,
            "power_factor": None,
            "active_power": None,
            "energy": None,
            "transaction_id": transaction_info.get("transaction_id"),
            "charging_state": transaction_info.get("charging_state"),
            "evse_id": evse.get("id"),
            "connector_id": evse.get("connector_id")
        }

        for mv in meter_values:
            for sv in mv.get("sampled_value", []):
                if sv["measurand"] == "Voltage":
                    transaction_data["voltage"] = sv["value"]
                elif sv["measurand"] == "Current.Export":
                    transaction_data["current"] = sv["value"]
                elif sv["measurand"] == "Frequency":
                    transaction_data["frequency"] = sv["value"]
                elif sv["measurand"] == "Power.Factor":
                    transaction_data["power_factor"] = sv["value"]
                elif sv["measurand"] == "Power.Active.Export":
                    transaction_data["active_power"] = sv["value"]
                elif sv["measurand"] == "Energy.Active.Export.Register":
                    transaction_data["energy"] = sv["value"]

        self._central_system.transaction_data[self.id] = transaction_data
        self._central_system.update_charger_data(self.id, {"charger_status": transaction_info.get("charging_state")})

        return call_result.TransactionEventPayload(
            total_cost=500.1234567,
            charging_priority=1,
            id_token_info={
                'status': "Accepted",
                'cacheExpiryDateTime': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z",
                'chargingPriority': 1,
                'language1': "English",
                'language2': "VN",
                'evseId': [123, 456, 789],
                'groupIdToken': {
                    'idToken': "Pass1234",
                    'type': "eMAID",
                    'additionalInfo': [
                        {
                            'additionalIdToken': "abc123xyz",
                            'type': "123abc"
                        },
                        {
                            'additionalIdToken': "0abc123xyz",
                            'type': "0123abc"
                        },
                        {
                            'additionalIdToken': "1abc123xyz",
                            'type': "a123abc"
                        }
                    ]
                },
                'personalMessage': {
                    'format': "UTF8",
                    'language': "English",
                    'content': "Final total cost of this transaction, including taxes"
                }
            },
            updated_personal_message={'format': 'ASCII', 'language': 'VN', 'content': 'abcxyz'}
        )

    @on("FirmwareStatusNotification")
    def on_firmware_status_notification(self, *args, **kwargs):
        logging.debug(f"Got a FirmwareStatusNotification kwargs: {kwargs}")
        return call_result.FirmwareStatusNotificationPayload()

    async def request_start_transaction_message(self, evse_id: int, id_token: str, remote_start_id: int):
        logging.debug("Sending request start transaction message")
        request = call.RequestStartTransactionPayload(
            evse_id=evse_id,
            group_id_token=
                {
                    'idToken':"Pass1234",
                    'type':"eMAID",
                    'additionalInfo':
                    [
                        {
                        'additionalIdToken':"abc123xyz",
                        'type':"123abc"
                        },
                        {
                        'additionalIdToken':"0abc123xyz",
                        'type':"0123abc"
                        },
                        {
                        'additionalIdToken':"1abc123xyz",
                        'type':"a123abc"
                        }
                    ]
                },
            id_token={'idToken': id_token, 'type': 'ISO14443'},
            remote_start_id=remote_start_id,
            charging_profile=
                {
                    'id':111,
                    'stack_level':1,
                    'charging_profile_purpose':'TxProfile',
                    'charging_profile_kind':'Absolute',
                    'charging_schedule':[
                    {
                        'id':321,
                        'charging_rate_unit':'W',
                        'charging_schedule_period':[
                        {
                            'start_period':1,
                            'limit':10.5,
                            'number_phases':3,
                            'phase_to_use':1
                        },
                        {
                            'start_period':2,
                            'limit':5.5,
                            'number_phases':1,
                            'phase_to_use':2
                        }
                        ],
                        'start_schedule':datetime.now(timezone.utc).isoformat(),
                        'duration':2,
                        'min_charging_rate':1,
                        'sales_tariff':{
                        'id':789,
                        'sales_tariff_entry':[
                            {
                                'relative_time_interval':{
                                    'start':1,
                                    'duration':2,
                                },
                                'consumption_cost':[
                                    {
                                    'start_value':1.1,
                                    'cost':[
                                        {
                                            'cost_kind':'CarbonDioxideEmission',
                                            'amount':6,
                                            'amount_multiplier':7
                                        },
                                        {
                                            'cost_kind':'RelativePricePercentage',
                                            'amount':3,
                                            'amount_multiplier':4
                                        }
                                    ]
                                    }
                                ],
                                'e_price_level':3
                            },
                            {
                                'relative_time_interval':{
                                    'start':2,
                                    'duration':1,
                                },
                                'consumption_cost':[
                                    {
                                    'start_value':2.2,
                                    'cost':[
                                        {
                                            'cost_kind':'RelativePricePercentage',
                                            'amount':7,
                                            'amount_multiplier':6
                                        }
                                    ]
                                    }
                                ],
                                'e_price_level':4
                            }
                        ],
                        'sales_tariff_description':"For example",
                        'num_e_price_levels':9
                        }
                    }
                    ],
                    'valid_from':datetime.now(timezone.utc).isoformat(),
                    'valid_to':(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                    'transaction_id':'abc123',
                    'recurrency_kind':'Daily'
                }
            )

        response = await self.call(request)
        logging.debug("Got request start transaction message response with transaction id: %s", response.transaction_id)
        return response

    async def request_stop_transaction_message(self, transaction_id: str):
        logging.debug("Sending request stop transaction message")
        request = call.RequestStopTransactionPayload(
            transaction_id=transaction_id
        )
        response = await self.call(request)
        logging.debug("Got request stop transaction message response!")
        return response

    async def trigger_message(self, requested_message: str, evse_id: int, connector_id: int):
        logging.debug("Sending trigger message")
        request = call.TriggerMessagePayload(
            requested_message=requested_message, evse={'id': evse_id, 'connectorId': connector_id}
        )
        response = await self.call(request)
        logging.debug("Got trigger message response!")
        return response
    
    async def change_availability(self, operation_status: str, evse_id: int, connector_id: int):
        logging.debug("Sending change availability message to %s", operation_status)
        request = call.ChangeAvailabilityPayload(
            operational_status=operation_status,
            evse={'id': evse_id, 'connectorId': connector_id}
        )
        response = await self.call(request)
        logging.debug("Got change availability message response!")
        return response

    async def reset_charger(self):
        logging.debug("Sending reset message")
        request = call.ResetPayload(type="Immediate", evse_id=123)
        response = await self.call(request)
        logging.debug("Got reset message response!")
        return response
    
    async def start(self):
        connection = self._connection
        try:
            await asyncio.gather(super().start())
        except Exception as e:
            self._central_system.update_charger_data(self.id, {"charger_status": "SuspendedEVSE"})
            logging.error(f"Charger {self.id} disconnected: {e}")
        finally:
            await connection.close()

    async def reconnect(self, connection):
        if self._connection.open:
            await self._connection.close()
            await asyncio.sleep(1)
        self._connection = connection
        try:
            await asyncio.gather(self.start())
        except Exception as e:
            self._central_system.update_charger_data(self.id, {"charger_status": "SuspendedEVSE"})
            logging.error(f"Charger {self.id} disconnected: {e}")
        finally:
            await connection.close()


class CentralSystem:
    def __init__(self):
        self._chargers = {}
        self.transaction_data = {}
        self.charger_data = self.load_charger_data()

    def register_charger(self, cp: ChargePoint):
        # Check if charger is already registered
        if cp.id in self._chargers:
            self.unregister_charger(cp.id)
        self._chargers[cp.id] = cp
        cp._central_system = self

    def unregister_charger(self, charger_id: str):
        if charger_id in self._chargers:
            logging.debug(f"Unregistering charger {charger_id}")
            del self._chargers[charger_id]

    def update_charger_data(self, cp_id: str, data: Dict[str, Any]):
        if cp_id in self.charger_data:
            self.charger_data[cp_id].update(data)
            logging.debug(f"Updated charger data for {cp_id}: {self.charger_data[cp_id]}")
            self.save_charger_data()

    def save_charger_data(self):
        with open("charger_data.json", "w") as file:
            json.dump(self.charger_data, file, indent=4, default=str)
        logging.debug("Saved charger data to disk.")

    def load_charger_data(self):
        try:
            with open("charger_data.json", "r") as file:
                logging.debug("Loading charger data from disk...")
                return json.load(file)
        except FileNotFoundError:
            logging.info("charger_data.json not found. Loading initial data.")
            return {
            'CP_1': {
                "id": "CP_1",
                "model": "AS054-1",
                "location": "HCM VN",
                "charger_status": "SuspendedEVSE",
                "lastUsed": "Jun 06, 08:37 PM",
                "note": "AS054-1 demo-in-box",
                "connectorType": "Type 2",
                "connectorStatus": "Available",
                "power": "7.7 kW",
                "lastSession": {
                    "dateTime": "Jun 05, 12:34 PM",
                    "status": "Completed",
                    "energy": 0.0,
                    "cost": "$5.67"
                }
            },
            'CP_2': {
                "id": "CP_2",
                "model": "AS054",
                "location": "BENGALURU IND",
                "charger_status": "SuspendedEVSE",
                "lastUsed": "Jun 06, 08:37 PM",
                "note": "AS054 demo-in-box",
                "connectorType": "Type 2",
                "connectorStatus": "Unavailable",
                "power": "7.7 kW",
                "lastSession": {
                    "dateTime": "Jun 05, 12:34 PM",
                    "status": "Completed",
                    "energy": 0.0,
                    "cost": "$5.67"
                }
            }
        }

    async def start_charger(self, cp: ChargePoint):
        try:
            await cp.start()
        except Exception as e:
            self.update_charger_data(cp.id, {"charger_status": "SuspendedEVSE"})
            logging.error(f"Charger {cp.id} disconnected: {e}")

    async def start_transaction(self, charge_point_id: str, evse_id: int, id_token: str, remote_start_id: int):
        logging.debug(f"Attempting to start transaction for {charge_point_id}")
        if charge_point_id in self._chargers:
            cp = self._chargers[charge_point_id]
            if self.charger_data[charge_point_id]["connectorStatus"] == "Occupied":
                self.update_charger_data(charge_point_id, {"charger_status": "Charging"})
            return await cp.request_start_transaction_message(evse_id, id_token, remote_start_id)
        raise ValueError(f"Charger {charge_point_id} not connected.")

    async def stop_transaction(self, charge_point_id: str, transaction_id: str):
        logging.debug(f"Attempting to stop transaction for {charge_point_id}")
        if charge_point_id in self._chargers:
            cp = self._chargers[charge_point_id]
            if self.charger_data[charge_point_id]["connectorStatus"] == "Occupied": # Available, Occupied, Reserved, Unavailable, Faulted
                self.update_charger_data(charge_point_id, {"charger_status": "Idle"})
            return await cp.request_stop_transaction_message(transaction_id)
        raise ValueError(f"Charger {charge_point_id} not connected.")
    
    async def get_transaction_info(self, charge_point_id: str, transaction_id: str = None):
        logging.debug(f"Getting transaction info for {charge_point_id} and {transaction_id}")
        if charge_point_id in self._chargers:
            if charge_point_id in self.transaction_data:
                if transaction_id:
                    if self.transaction_data[charge_point_id]["transaction_id"] == transaction_id:
                        return self.transaction_data[charge_point_id]
                else:
                    return self.transaction_data[charge_point_id]
        raise ValueError(f"Charger {charge_point_id} not connected.")

    async def trigger_message(self, charge_point_id: str, requested_message: str, evse_id: int, connector_id: int):
        logging.debug(f"Triggering message {requested_message} for {charge_point_id}")
        if charge_point_id in self._chargers:
            cp = self._chargers[charge_point_id]
            return await cp.trigger_message(requested_message, evse_id, connector_id)
        raise ValueError(f"Charger {charge_point_id} not connected.")
    
    async def change_availability(self, charge_point_id: str, operation_status: str, evse_id: int, connector_id: int):
        logging.debug(f"Changing availability to {operation_status} for {charge_point_id}")
        if charge_point_id in self._chargers:
            cp = self._chargers[charge_point_id]
            return await cp.change_availability(operation_status, evse_id, connector_id)
        raise ValueError(f"Charger {charge_point_id} not connected.")

    async def reset_charger(self, charge_point_id: str):
        logging.debug(f"Attempting to reset charger {charge_point_id}")
        if charge_point_id in self._chargers:
            cp = self._chargers[charge_point_id]
            if self.charger_data[charge_point_id]["connectorStatus"] == "Occupied": # Available, Occupied, Reserved, Unavailable, Faulted
                self.update_charger_data(charge_point_id, {"charger_status": "SuspendedEVSE"})
            return await cp.reset_charger()
        raise ValueError(f"Charger {charge_point_id} not connected.")

    def add_charger(self, charger_id: str, data: Dict[str, Any]):
        if charger_id in self.charger_data:
            raise ValueError(f"Charger {charger_id} already exists.")
        self.charger_data[charger_id] = data
        logging.debug(f"Added new charger with id {charger_id}: {data}")
        self.save_charger_data()

    def edit_charger(self, charger_id: str, data: Dict[str, Any]):
        if charger_id not in self.charger_data:
            raise ValueError(f"Charger {charger_id} not found.")
        self.charger_data[charger_id].update(data)
        logging.debug(f"Updated charger with id {charger_id}: {self.charger_data[charger_id]}")
        self.save_charger_data()


app = FastAPI()

csms = CentralSystem()

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StartTransactionRequest(BaseModel):
    charge_point_id: str
    evse_id: int
    id_token: str
    remote_start_id: int

class StopTransactionRequest(BaseModel):
    charge_point_id: str
    transaction_id: str

class TriggerMessageRequest(BaseModel):
    charge_point_id: str
    requested_message: str
    evse_id: int
    connector_id: int

class ChangeAvailabilityRequest(BaseModel):
    charge_point_id: str
    operation_status: str
    evse_id: int
    connector_id: int

class ResetRequest(BaseModel):
    charge_point_id: str

# Sample data classes
class LastSession(BaseModel):
    dateTime: str
    status: str
    energy: float
    cost: str

class Charger(BaseModel):
    id: str
    model: str
    location: str
    charger_status: str
    lastUsed: str
    note: str
    connectorType: str
    connectorStatus: str
    power: str
    lastSession: LastSession

@app.get("/api/chargers", response_model=List[Charger])
async def get_chargers():
    return list(csms.charger_data.values())

@app.get("/api/chargers/{id}", response_model=Charger)
async def get_charger(id: str):
    charger = csms.charger_data.get(id)
    if charger:
        return charger
    else:
        raise HTTPException(status_code=404, detail="Charger not found")

@app.post("/api/chargers", response_model=Charger)
async def add_charger(charger: Charger):
    try:
        csms.add_charger(charger.id, charger.dict())
        return charger
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/chargers/{id}", response_model=Charger)
async def edit_charger(id: str, charger: Charger):
    try:
        csms.edit_charger(id, charger.dict())
        return charger
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/locations", response_model=List[str])
async def get_locations():
    return ["HCM VN", "BENGALURU IND", "Another Location"]

@app.get("/api/charging_state", response_model=List[str])
async def get_charging_state():
    return ["Idle", "Charging", "EVConnected", "SuspendedEVSE", "SuspendedEV"]

@app.get("/api/connector_status", response_model=List[str])
async def get_connector_status():
    return ["Available", "Occupied", "Reserved", "Unavailable", "Faulted"]

@app.post("/start_transaction")
async def start_transaction(request: StartTransactionRequest):
    try:
        result = await csms.start_transaction(
            request.charge_point_id,
            request.evse_id,
            request.id_token,
            request.remote_start_id
        )
        return result
    except ValueError as e:
        logging.error(f"Failed to start transaction: {e}")
        raise HTTPException(status_code=404, detail="Charger not connected")

@app.post("/stop_transaction")
async def stop_transaction(request: StopTransactionRequest):
    try:
        logging.debug(f"Stopping transaction {request.transaction_id}")
        result = await csms.stop_transaction(
            request.charge_point_id,
            request.transaction_id
        )
        logging.debug(f"Transaction {request.transaction_id} stopped")
        return {"status": "Transaction stopped", "result": result}
    except ValueError as e:
        logging.error(f"Failed to stop transaction: {e}")
        raise HTTPException(status_code=404, detail="Charger not connected")

@app.get("/transaction_info")
async def get_transaction_info(charge_point_id: str = Query(...), transaction_id: str = Query(None)):
    logging.debug(f"Getting transaction info for {charge_point_id} and {transaction_id}")
    try:
        result = await csms.get_transaction_info(
            charge_point_id,
            transaction_id
        )
        return result
    except ValueError as e:
        logging.error(f"Failed to get transaction info: {e}")
        raise HTTPException(status_code=404, detail="Transaction not found")

@app.post("/trigger_message")
async def trigger_message(request: TriggerMessageRequest):
    try:
        result = await csms.trigger_message(
            request.charge_point_id,
            request.requested_message,
            request.evse_id,
            request.connector_id
        )
        return {"status": "Message triggered", "result": result}
    except ValueError as e:
        logging.error(f"Failed to trigger message: {e}")
        raise HTTPException(status_code=404, detail="Charger not connected")

@app.post("/change_availability")
async def change_availability(request: ChangeAvailabilityRequest):
    logging.debug(f"Changing availability to {request.operation_status} for {request.charge_point_id} {request.evse_id} {request.connector_id}")
    try:
        result = await csms.change_availability(
            request.charge_point_id,
            request.operation_status,
            request.evse_id,
            request.connector_id
        )
        return {"status": "Availability changed", "result": result}
    except ValueError as e:
        logging.error(f"Failed to change availability: {e}")
        raise HTTPException(status_code=404, detail="Charger not connected")

@app.post("/reset")
async def reset_charger(request: ResetRequest):
    try:
        result = await csms.reset_charger(
            request.charge_point_id
        )
        return {"status": "Charger reset", "result": result}
    except ValueError as e:
        logging.error(f"Failed to reset charger: {e}")
        raise HTTPException(status_code=404, detail="Charger not connected")

async def on_connect(websocket, path):
    charge_point_id = path.strip("/")
    if charge_point_id not in csms._chargers:
        cp = ChargePoint(charge_point_id, websocket, csms)
        csms.register_charger(cp)
        await csms.start_charger(cp)
    else:
        charge_point: ChargePoint = csms._chargers[charge_point_id]
        await charge_point.reconnect(websocket)

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
ssl_context.load_cert_chain('../server.crt', '../server.key')
ssl_context.set_ciphers('ECDHE-ECDSA-AES256-SHA:AES256-SHA256')

async def main():
    server = websockets.serve(
        #on_connect, "0.0.0.0", 8443, ssl=ssl_context, subprotocols=["ocpp2.0.1"]
        on_connect, "0.0.0.0", 8443, subprotocols=["ocpp2.0.1"]
    )

    config = Config(app=app, host="0.0.0.0", port=8446, log_level="info")
    fastapi_server = Server(config=config)

    await asyncio.gather(server, fastapi_server.serve())

if __name__ == "__main__":
    asyncio.run(main())
