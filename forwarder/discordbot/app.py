import asyncio, os, socket, time
import discord
from discord.ext import commands
import aio_pika
from models import *
from forwarder import Forwarder, forward_notifs

POSTGRES_USER = os.environ['POSTGRES_USER']
POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']
RABBITMQ_USER = os.environ['RABBITMQ_USER']
RABBITMQ_PASSWORD = os.environ['RABBITMQ_PASSWORD']
DISCORD_TOKEN = os.environ['DISCORD_TOKEN']

def wait_for_port(host, port):
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                break
        except:
            time.sleep(3)

async def main():
    wait_for_port('forwarder-postgres', 5432)
    wait_for_port('forwarder-rabbit', 5672)

    connection = await aio_pika.connect_robust(
        f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@forwarder-rabbit/'
    )

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=5)
    notifs = await channel.declare_queue('notifs')

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='>', intents=intents)
    forwarder = Forwarder(bot)
    await bot.add_cog(forwarder)

    asyncio.create_task(forward_notifs(forwarder, notifs))

    await bot.start(DISCORD_TOKEN, reconnect=True)

if __name__ == '__main__':
    asyncio.run(main())
