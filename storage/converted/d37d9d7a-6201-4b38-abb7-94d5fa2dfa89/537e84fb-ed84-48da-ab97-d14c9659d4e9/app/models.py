from extensions import db


class Item(db.Model):
    __tablename__ = 'item'
    name = db.Column(String, length = 100)
    price = db.Column(Integer)

    def __str__(self):
        return self.name
