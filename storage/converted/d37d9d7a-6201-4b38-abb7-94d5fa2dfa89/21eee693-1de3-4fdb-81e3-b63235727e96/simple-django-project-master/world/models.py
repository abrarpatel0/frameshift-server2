from extensions import db
from flask_login import UserMixin

# Models recovered from Django code with syntax errors
# Manual review recommended

class City(db.Model):
    __tablename__ = 'city'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(35))
    countrycode = db.Column(db.String(3), db.ForeignKey('country.code'))
    district = db.Column(db.String(20))
    population = db.Column(db.Integer)

    def __repr__(self):
        return f'<City {getattr(self, "id", None)}>'

class Country(db.Model):
    __tablename__ = 'country'

    code = db.Column(db.String(3), primary_key=True)
    name = db.Column(db.String(52))
    continent = db.Column(db.String(13))
    region = db.Column(db.String(26))
    surfacearea = db.Column(db.Float)
    indepyear = db.Column(db.SmallInteger, nullable=True)
    population = db.Column(db.Integer)
    lifeexpectancy = db.Column(db.Float, nullable=True)
    gnp = db.Column(db.Float, nullable=True)
    gnpold = db.Column(db.Float, nullable=True)
    localname = db.Column(db.String(45))
    governmentform = db.Column(db.String(45))
    headofstate = db.Column(db.String(60), nullable=True)
    capital = db.Column(db.Integer, nullable=True)
    code2 = db.Column(db.String(2))

    def __repr__(self):
        return f'<Country {getattr(self, "id", None)}>'

class Countrylanguage(db.Model):
    __tablename__ = 'countrylanguage'

    countrycode = db.Column(db.String(3), db.ForeignKey('country.code'), primary_key=True)
    language = db.Column(db.String(30))
    isofficial = db.Column(db.String(1))
    percentage = db.Column(db.Float)

    def __repr__(self):
        return f'<Countrylanguage {getattr(self, "id", None)}>'

class DjangoMigrations(db.Model):
    __tablename__ = 'django_migrations'

    app = db.Column(db.String(255))
    name = db.Column(db.String(255))
    applied = db.Column(db.DateTime)

    def __repr__(self):
        return f'<DjangoMigrations {getattr(self, "id", None)}>'

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100), nullable=True)
    username = db.Column(db.String(100), nullable=True)
    gender = db.Column(db.String(100), default='female')
    email = db.Column(db.String(100), primary_key=True)
    phone_number = db.Column(db.String(32))

    def __repr__(self):
        return f'<User {getattr(self, "id", None)}>'
