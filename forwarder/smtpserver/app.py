import asyncio
import base64
import pika
import aiosmtpd.controller
import aiosmtpd.smtp as smtp
import json
import os

class SMTPForwarder:
    def __init__(self, conn: pika.BlockingConnection) -> None:
        self.conn = conn
        self.channel = self.conn.channel()
        self.channel.queue_declare('emails')
    
    def send_message(self, message):
        if self.channel is None:
            self.channel = self.conn.channel()
            self.channel.queue_declare('emails')
        self.channel.basic_publish('', 'emails', json.dumps(message))

    async def handle_DATA(self, server: smtp.SMTP, session: smtp.Session, envelope: smtp.Envelope) -> str:
        print(f'New incoming email from {envelope.mail_from} to {envelope.rcpt_tos}')

        data = envelope.content
        if data is None:
            data = b''
        if isinstance(data, str):
            data = data.encode()

        mail_object = {
            'recipients': envelope.rcpt_tos,
            'sender': envelope.mail_from,
            'content': base64.b64encode(data).decode()
        }
        
        self.send_message(mail_object)

        return '250 OK'

async def main(loop):
    while True:
        print('Trying to connect to rabbitmq...')
        try:
            credentials = pika.PlainCredentials(os.environ['RABBITMQ_USER'], os.environ['RABBITMQ_PASSWORD'])
            connection = pika.BlockingConnection(
                pika.ConnectionParameters('forwarder-rabbit', 5672, '/', credentials, heartbeat=0)
            )
            print('Connected!')
            break
        except:
            print('Failed, retrying in 3s')
            await asyncio.sleep(3)

    handler = SMTPForwarder(connection)
    server = aiosmtpd.controller.Controller(handler, hostname='0.0.0.0', port=25)
    server.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main(loop=loop))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
