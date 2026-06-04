import asyncio
import os

import firebase_admin
from firebase_admin import credentials, messaging


def init_firebase() -> None:
    if firebase_admin._apps:
        return
    service_account_path = os.environ["FIREBASE_SERVICE_ACCOUNT"]
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)


async def send_data_message(data: dict[str, str]) -> str:
    init_firebase()
    message = messaging.Message(
        token=os.environ["FCM_DEVICE_TOKEN"],
        data={key: str(value) for key, value in data.items()},
        android=messaging.AndroidConfig(priority="high"),
    )
    return await asyncio.to_thread(messaging.send, message)

