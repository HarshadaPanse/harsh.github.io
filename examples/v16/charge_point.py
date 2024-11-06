import asyncio
import logging
import ssl

try:
    import websockets
except ModuleNotFoundError:
    print("This example relies on the 'websockets' package.")
    print("Please install it by running: ")
    print()
    print(" $ pip install websockets")
    import sys

    sys.exit(1)


from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call
from ocpp.v16.enums import RegistrationStatus

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):
    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charge_point_model="Optimus", charge_point_vendor="The Mobility House"
        )

        response = await self.call(request)

        if response.status == RegistrationStatus.accepted:
            print("Connected to central system.")


async def main():
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_verify_locations("/home/u/chungnguyen/ocpp_mobilityhouse/examples/v16/ca.pem")
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with websockets.connect(
        "wss://localhost:8080/CP_1", ssl=ssl_context, subprotocols=["ocpp1.6"]
    ) as ws:

        cp = ChargePoint("CP_1", ws)

        await asyncio.gather(cp.start(), cp.send_boot_notification())


if __name__ == "__main__":
    # asyncio.run() is used when running this example with Python >= 3.7v
    asyncio.run(main())
