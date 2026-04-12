"""Flask app extension initialization."""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)
mail = Mail()


def init_app_extensions(app):
    """Initialize all Flask extensions with app."""
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={
            r"/api/*": {"origins": app.config.get("CORS_ORIGINS", ["http://localhost:3001"])},
            r"/health": {"origins": app.config.get("CORS_ORIGINS", ["http://localhost:3001"])},
        },
        supports_credentials=True,
    )
    limiter.init_app(app)
    mail.init_app(app)

    return {
        "db": db,
        "jwt": jwt,
        "cors": cors,
        "limiter": limiter,
        "mail": mail,
    }
