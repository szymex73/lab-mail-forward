import base64, json, os, queue, re, math, textwrap
from email.message import Message
from email import message_from_bytes
from typing import Callable
import asyncpg # pyright: reportMissingImports=false
from discord.ext import commands, tasks
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.sql.expression import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.session import sessionmaker
import aio_pika
from models import *

POSTGRES_USER = os.environ['POSTGRES_USER']
POSTGRES_PASSWORD = os.environ['POSTGRES_PASSWORD']

bind = create_async_engine(f'postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@forwarder-postgres/forwarder')
sm: Callable[[], AsyncSession] = sessionmaker(bind, AsyncSession, expire_on_commit=False)

email_re = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

class Forwarder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pending = queue.Queue()
        self.notifier.start()
    
    async def find_user_by_mail(self, session: AsyncSession, email: str) -> User:
        rows = (await session.execute(select(Address).filter_by(address=email).options(selectinload(Address.user)))).first()
        if not rows or len(rows) != 1:
            return None
        return rows[0].user

    async def find_user_by_id(self, session: AsyncSession, id: int) -> User:
        rows = (await session.execute(select(User).filter_by(discord_id=str(id)).options(selectinload(User.addresses)))).first()
        if not rows or len(rows) != 1:
            return None
        return rows[0]
    
    async def get_user_emails(self, user: User) -> list[str]:
        return [addr.address for addr in user.addresses]
    
    async def find_email_by_id(self, session: AsyncSession, email_id: int) -> Email:
        rows = (await session.execute(select(Email).filter_by(id=email_id))).first()
        if not rows or len(rows) != 1:
            return None
        return rows[0]
    
    async def get_email_count_for_addresses(self, session: AsyncSession, emails: list[str]) -> int:
        return (await session.execute(
            select(func.count()).select_from(Email).filter(Email.rcpt.in_(emails))
        )).first()[0]
    
    async def find_latest_x_emails_by_addresses(self, session: AsyncSession, emails: list[str], count: int, offset: int) -> list[Email]:
        rows = (await session.execute(
            select(Email)
                .filter(Email.rcpt.in_(emails))
                .order_by(Email.id.desc())
                .limit(count)
                .offset(offset * count)
        )).all()
        if not rows:
            return None
        return rows
    
    def get_email_body(self, email: Message) -> str:
        body = ""
        if email.is_multipart():
            for part in email.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))

                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    body = part.get_payload(decode=True)
                    break
        else:
            body = email.get_payload(decode=True)
        return body
    
    @commands.group(name='alias', invoke_without_command=True)
    async def alias_group(self, ctx: commands.Context):
        await ctx.send(textwrap.dedent("""
        ```
        Available subcommands
        >alias list
        >alias add <email@domain.com>
        >alias remove <email@domain.com>
        ```
        """))
    
    @alias_group.command(name='list')
    async def alias_list(self, ctx: commands.Context):
        author_id = ctx.author.id

        async with sm() as session:
            user = await self.find_user_by_id(session, author_id)
            if not user:
                await ctx.send("You don't currently have any added aliases")
                return
            
            msg = "Current aliases for your account:\n```"
            for addr in user.addresses:
                msg += f'- {addr.address}\n'
            msg += '```'
            await ctx.send(msg)
    
    @alias_group.command(name='add')
    async def alias_add(self, ctx: commands.Context, email: str):
        author_id = ctx.author.id
        
        async with sm() as session:
            user = await self.find_user_by_id(session, author_id)
            if not user:
                user = User(discord_id=str(author_id))
                session.add(user)
                await session.commit()
            
            if not email_re.match(email):
                await ctx.send('The given alias is invalid')
                return
            
            temp = await self.find_user_by_mail(session, email)
            if temp:
                await ctx.send('The given alias is already taken')
                return
            
            address = Address(address=email, user_id=user.id)
            session.add(address)
            await session.commit()

            await ctx.send(f'Succesfully added `{email}` to your account')

    @alias_group.command(name='remove')
    async def alias_remove(self, ctx: commands.Context, email: str):
        author_id = ctx.author.id
        
        async with sm() as session:
            user = await self.find_user_by_id(session, author_id)
            if not user:
                user = User(discord_id=str(author_id))
                session.add(user)
                await session.commit()
            
            if not email_re.match(email):
                await ctx.send('The given alias is invalid')
                return
            
            temp = await self.find_user_by_mail(session, email)
            if not temp:
                await ctx.send('The given alias is not used')
                return
            
            if temp.id != user.id:
                await ctx.send('The given alias does not belong to you')
                return
            
            rows = (await session.execute(select(Address).filter_by(address=email))).first()
            if not rows or len(rows) != 1:
                return None
            address = rows[0]

            await session.delete(address)
            await session.commit()

            await ctx.send(f'Succesfully removed `{email}` from your account')

    @commands.group(name='email', invoke_without_command=True)
    async def emails_group(self, ctx: commands.Context):
        await ctx.send(textwrap.dedent("""
        ```
        Available subcommands
        >email list [page]
        >email view <id>
        ```
        """))

    page_size = 10
    @emails_group.command(name='list')
    async def email_list(self, ctx: commands.Context, page: int = 1):
        author_id = ctx.author.id

        async with sm() as session:
            try:
                user = await self.find_user_by_id(session, author_id)
                if not user:
                    user = User(discord_id=str(author_id))
                    session.add(user)
                    await session.commit()
                
                addresses = await self.get_user_emails(user)

                email_count = await self.get_email_count_for_addresses(session, addresses)
                if page < 1 or math.ceil(email_count / Forwarder.page_size) < page:
                    await ctx.send("There is no such page")
                    return
                
                emails = await self.find_latest_x_emails_by_addresses(session, addresses, Forwarder.page_size, page - 1)
                if not emails:
                    await ctx.send("Your inbox is empty")
                    return
                
                resp = f"Showing page {page} / {math.ceil(email_count / Forwarder.page_size)} (Total {email_count} emails, showing {Forwarder.page_size} per page)\n"
                resp += "```\n id | [From] Subject\n"
                for email in emails:
                    email = email[0]
                    mail = message_from_bytes(base64.b64decode(email.content))
                    subject = mail.get('Subject', 'No subject')
                    resp += f'{email.id:3d} | [{email.sender}] {subject}\n'
                resp += '```'
                
                await ctx.send(resp)
            except Exception as e:
                print(e.with_traceback(None))


    @emails_group.command(name='view')
    async def email_view(self, ctx: commands.Context, id: int):
        author_id = ctx.author.id

        async with sm() as session:
            user = await self.find_user_by_id(session, author_id)
            if not user:
                user = User(discord_id=str(author_id))
                session.add(user)
                await session.commit()
            
            addresses = await self.get_user_emails(user)

            email = await self.find_email_by_id(session, id)
            if not email:
                await ctx.send("That email does not exist")
                return
            
            if email.rcpt not in addresses:
                await ctx.send("That email does not exist")
                return
            
            mail = message_from_bytes(base64.b64decode(email.content))
            subject = mail.get('Subject', 'No subject')
            
            await ctx.send(f"""
            To: `{email.rcpt}`
            From: `{email.sender}`
            Subject: `{subject}`
            ```
            {self.get_email_body(mail).decode()}
            ```
            """.replace('\n            ', '\n'))

    @tasks.loop(seconds=10)
    async def notifier(self):
        if self.pending.empty():
            return

        async with sm() as session:
            while not self.pending.empty():
                try:
                    data = self.pending.get()
                    recipient = data['recipient']
                    sender = data['sender']
                    subject = data['subject']
                    id = data['id']

                    user = await self.find_user_by_mail(session, recipient)
                    if not user:
                        continue

                    d_user = await self.bot.fetch_user(int(user.discord_id))
                    try:
                        await d_user.send(f':incoming_envelope: New email from `{sender}` on `{recipient}`!\nSubject: `{subject}`\nView with `>email view {id}`')
                    except:
                        print(f'Error while notifying owner of email {recipient}')
                except Exception as e:
                    print(e.with_traceback(None))

async def forward_notifs(forwarder: Forwarder, notifs: aio_pika.abc.AbstractQueue):
    async with notifs.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    data = json.loads(message.body)
                    forwarder.pending.put(data)
                except Exception as e:
                    print(e.with_traceback(None))
