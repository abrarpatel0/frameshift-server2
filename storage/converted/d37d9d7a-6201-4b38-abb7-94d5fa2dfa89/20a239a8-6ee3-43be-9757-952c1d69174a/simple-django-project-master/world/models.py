from extensions import db
from flask_login import UserMixin

# Last-resort fallback generated from malformed Django model source.
# Manual review is required.

class City(db.Model):
    __tablename__ = 'city'
    id = db.Column(db.Integer, primary_key=True)
    # TODO: Manual field reconstruction required - source model file is malformed.

class Country(db.Model):
    __tablename__ = 'country'
    id = db.Column(db.Integer, primary_key=True)
    # TODO: Manual field reconstruction required - source model file is malformed.

class Countrylanguage(db.Model):
    __tablename__ = 'countrylanguage'
    id = db.Column(db.Integer, primary_key=True)
    # TODO: Manual field reconstruction required - source model file is malformed.

class DjangoMigrations(db.Model):
    __tablename__ = 'djangomigrations'
    id = db.Column(db.Integer, primary_key=True)
    # TODO: Manual field reconstruction required - source model file is malformed.

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    # TODO: Manual field reconstruction required - source model file is malformed.
