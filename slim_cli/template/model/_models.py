from model import db
from model.example import Example

db.connect()
db.create_tables([Example], safe=True)
