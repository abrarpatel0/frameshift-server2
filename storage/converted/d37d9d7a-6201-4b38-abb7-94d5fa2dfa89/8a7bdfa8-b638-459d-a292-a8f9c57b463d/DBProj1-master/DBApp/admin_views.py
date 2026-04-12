from flask_admin.contrib.sqla import ModelView
from extensions import db
from .models import *

class StudentAdminView(ModelView):

    pass  # Auto-mapped from admin.site.register

def init_admin_views(admin_app):
    admin_app.add_view(StudentAdminView(Student, db.session))
