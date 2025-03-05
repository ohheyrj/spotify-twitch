from flask import Flask
from app.config import Config
from app.extensions import db, scheduler, migrate
from app.models import init_cipher
from app.logging import setup_logging

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['SCHEDULER_API_ENABLED'] = True

    logger = setup_logging(app)
    logger.info('Application Starting')

    global app_instance
    app_instance = app

    db.init_app(app)
    migrate.init_app(app, db)
    init_cipher(app)

    with app.app_context():
        db.create_all()

    from app.routes import main
    app.register_blueprint(main)

    scheduler.init_app(app)
    scheduler.start()

    # Initialize scheduler jobs
    from app.tasks import init_scheduler
    init_scheduler(app)

    return app
