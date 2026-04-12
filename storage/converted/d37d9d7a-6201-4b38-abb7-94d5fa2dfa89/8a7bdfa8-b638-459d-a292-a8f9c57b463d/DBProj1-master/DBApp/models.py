from extensions import db


# Create your models here.

class Student(db.Model):
	__tablename__ = 'student'
	name = db.Column(String, length = 100)
	email = db.Column(String, length = 254)
	age = db.Column(Integer)
	joined_date = db.Column(Date)

	def __str__(self):
		return self.name +"  "+ self.email

