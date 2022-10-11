import asyncio, base64, email, json, os, socket, time
import asyncpg # pyright: reportMissingImports=false
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm.session import sessionmaker
import aio_pika
from models import *

POSTGRES_USER = os.environ['POSTGRES_USER']
POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']
RABBITMQ_USER = os.environ['RABBITMQ_USER']
RABBITMQ_PASSWORD = os.environ['RABBITMQ_PASSWORD']

def wait_for_port(host, port):
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                break
        except:
            time.sleep(3)

bind = create_async_engine(f'postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@forwarder-postgres/forwarder')

async def main():
    wait_for_port('forwarder-postgres', 5432)
    wait_for_port('forwarder-rabbit', 5672)

    async with bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    connection = await aio_pika.connect_robust(
        f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@forwarder-rabbit/'
    )

    async with connection:
        channel = await connection.channel()

        await channel.set_qos(prefetch_count=5)

        emails = await channel.declare_queue('emails')
        notifs = await channel.declare_queue('notifs')

        async with emails.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        data = json.loads(message.body)
                        recipient = data['recipients'][0]
                        sender = data['sender']
                        mail = email.message_from_bytes(base64.b64decode(data['content']))
                        subject = mail.get('Subject', 'No subject')

                        sm = sessionmaker(bind, AsyncSession, expire_on_commit=False)
                        async with sm() as session:
                            new_mail = Email(
                                sender=sender,
                                content=data['content'],
                                rcpt=recipient
                            )
                            session.add(new_mail)
                            await session.commit()
                        
                        notif_obj = {
                            'sender': sender,
                            'recipient': recipient,
                            'subject': subject,
                            'id': new_mail.id
                        }

                        await channel.default_exchange.publish(
                            aio_pika.Message(body=json.dumps(notif_obj).encode()),
                            routing_key='notifs'
                        )
                    except Exception as e:
                        print('Error occured while processing an email')
                        print(data)
                        print(e)

if __name__ == '__main__':
    asyncio.run(main())