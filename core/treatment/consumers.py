import json

from channels.generic.websocket import AsyncWebsocketConsumer


class DoctorQueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        doctor_id = self.scope["url_route"]["kwargs"].get("doctor_id")
        self.group_name = f"doctor_queue_{doctor_id or 'all'}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Dashboard stream is server-driven; keep receive as no-op.
        return

    async def queue_update(self, event):
        await self.send(text_data=json.dumps({"type": "queue_update", "message": event["message"]}))
