import os
from cryptography.fernet import Fernet

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    DB_NAME = os.environ.get('DB_NAME')
    DB_USERNAME = os.environ.get('DB_USERNAME')
    DB_HOST = os.environ.get('DB_HOST')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    SQLALCHEMY_DATABASE_URI = f'mysql+mysqlconnector://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    SPOTIFY_SCOPES = "user-read-private user-read-email user-read-currently-playing playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private playlist-modify-public playlist-modify-private"
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', 'your_spotify_client_id')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', 'your_spotify_client_secret')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback')
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24))
    TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID', 'your_twitch_client_id')
    TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET', 'your_twitch_client_secret')
    TWITCH_REDIRECT_URI = os.getenv('TWITCH_REDIRECT_URI', 'http://localhost:5000/twitch_callback')
    TWITCH_SCOPES = "chat:read chat:edit user:read:moderated_channels"
