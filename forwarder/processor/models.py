from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import INTEGER, String

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    id = Column(INTEGER, primary_key=True)

class User(BaseModel):
    __tablename__ = 'users'
    discord_id = Column(String)

class Address(BaseModel):
    __tablename__ = 'addresses'
    address = Column(String, unique=True)
    user_id = Column(INTEGER, ForeignKey('users.id'))

class Email(BaseModel):
    __tablename__ = 'emails'
    sender = Column(String)
    content = Column(String)
    rcpt = Column(String) # Not forcing a fkey so that we can accept unknown emails as well
