from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
scheduler = APScheduler()
app_instance = None
active_bots = {}
