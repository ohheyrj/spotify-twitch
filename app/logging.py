import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(app):
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Set up file handler
    file_handler = RotatingFileHandler(
        'logs/app.log', 
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    
    # Set formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    file_handler.setFormatter(formatter)

    # Set log level
    file_handler.setLevel(logging.INFO)
    
    # Add handler to Flask logger
    app.logger.addHandler(file_handler)
    
    # Set Flask logger level
    app.logger.setLevel(logging.INFO)
    
    # Also handle werkzeug (Flask's built-in server) logs
    logging.getLogger('werkzeug').addHandler(file_handler)

    return app.logger
