import asyncio
import logging
from datetime import datetime

try:
    import websockets
except ModuleNotFoundError:
    print("This example relies on the 'websockets' package.")
    print("Please install it by running: ")
    print()
    print(" $ pip install websockets")
    import sys

    sys.exit(1)

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus

logging.basicConfig(level=logging.INFO)  # Set logging level to INFO/DEBUG

class ChargePoint(cp):
    async def route_message(self, message):
        print(f"Received: {message}")
        await super().route_message(message)

    @on(Action.BootNotification)
    def on_boot_notification(
        self, charge_point_vendor: str, charge_point_model: str, **kwargs
    ):
        logging.debug("Received boot notification from %s %s", charge_point_vendor, charge_point_model)
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )

    @on(Action.Heartbeat)
    def on_heartbeat(self):
        """Respond to a Heartbeat request."""
        logging.debug("Received heartbeat")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )

async def on_connect(websocket, path):
    """For every new charge point that connects, create a ChargePoint
    instance and start listening for messages.
    """
    logging.debug("New connection from %s", path)
    try:
        requested_protocols = websocket.request_headers["Sec-WebSocket-Protocol"]
    except KeyError:
        logging.error("Client hasn't requested any Subprotocol. Closing Connection")
        return await websocket.close()
    if websocket.subprotocol:
        logging.info("Protocols Matched: %s", websocket.subprotocol)
    else:
        # In the websockets lib if no subprotocols are supported by the
        # client and the server, it proceeds without a subprotocol,
        # so we have to manually close the connection.
        logging.warning(
            "Protocols Mismatched | Expected Subprotocols: %s,"
            " but client supports  %s | Closing connection",
            websocket.available_subprotocols,
            requested_protocols,
        )
        return await websocket.close()

    charge_point_id = path.strip("/")
    cp = ChargePoint(charge_point_id, websocket)

    logging.debug("Starting charge point %s", charge_point_id)
    await cp.start()

import ssl
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
# ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
# ssl_context.load_cert_chain('/home/u/chungnguyen/ocpp_mobilityhouse/__gen_crt/02/server.crt', '/home/u/chungnguyen/ocpp_mobilityhouse/__gen_crt/02/server.key')
ssl_context.load_cert_chain('../server.crt', '../server.key')
ssl_context.set_ciphers('ECDHE-ECDSA-AES256-SHA:ECDHE-ECDSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:AES256-SHA256')

async def main():
    server = await websockets.serve(
        # on_connect, "0.0.0.0", 8080, subprotocols=["ocpp1.6"]
        on_connect, "0.0.0.0", 8443, ssl=ssl_context, subprotocols=["ocpp1.6"]
    )

    logging.debug("Server Started listening to new connections...")
    await server.wait_closed()


if __name__ == "__main__":
    # asyncio.run() is used when running this example with Python >= 3.7v
    asyncio.run(main())
