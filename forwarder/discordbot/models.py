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
    addresses = relationship('Address', back_populates="user")

# Separate table instead of it being a member of User because
# I plan on supporting multiple emails per user + other features
class Address(BaseModel):
    __tablename__ = 'addresses'
    address = Column(String, unique=True)
    user_id = Column(INTEGER, ForeignKey('users.id'))

    user = relationship('User', back_populates='addresses')

class Email(BaseModel):
    __tablename__ = 'emails'
    sender = Column(String)
    content = Column(String)
    rcpt = Column(String) # Not forcing a fkey so that we can accept unknown emails as well
