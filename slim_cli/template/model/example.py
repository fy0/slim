from peewee import *
from model import BaseModel


class Example(BaseModel):
    test = TextField()

    class Meta:
        db_table = 'example'
