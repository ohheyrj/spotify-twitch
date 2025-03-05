from cryptography.fernet import Fernet
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from .extensions import db
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
import requests
import base64
from .config import Config
from flask import current_app

Base = declarative_base()
cipher = None

def init_cipher(app):
    global cipher
    cipher = Fernet(app.config['ENCRYPTION_KEY'].encode())

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    spotify_uri = db.Column(db.String(255), unique=True, nullable=True) # uri from Spotify API
    twitch_uri = db.Column(db.String(255), unique=True, nullable=True) # id from Twitch API
    spotify_display_name = db.Column(db.String(255), nullable=True) # display_name from Spotify API
    twitch_display_name = db.Column(db.String(255), nullable=True) # display_name from Twitch API
    spotify_display_picture = db.Column(db.Text(), nullable=True) # images[0]url from Spotify API
    twitch_display_picture = db.Column(db.Text(), nullable=True) # profile_image_url from Twitch API
    twitch_monitored_channel = db.Column(db.String(255), nullable=True)
    spotify_add_to_playlist = db.Column(db.Boolean(), default=False)
    spotify_playlist_id = db.Column(db.String(255), nullable=True)
    twitch_monitored_channel_is_live = db.Column(db.Boolean(), default=False)
class SpotifyToken(db.Model):
    __tablename__ = 'spotify_tokens'
    id = db.Column(db.Integer, primary_key=True)
    spotify_uri = db.Column(db.String(255), ForeignKey(User.spotify_uri))
    spotify_access_token = db.Column(db.LargeBinary, nullable=True)
    spotify_refresh_token = db.Column(db.LargeBinary, nullable=True)
    spotify_token_expiration = db.Column(db.DateTime, nullable=True)

    user = relationship("User")

    def set_spotify_tokens(self, access, refresh, expires_in):
        self.spotify_access_token = cipher.encrypt(access.encode())
        self.spotify_refresh_token = cipher.encrypt(refresh.encode())
        self.spotify_token_expiration = datetime.utcnow() + timedelta(seconds=expires_in)

    def get_decrypted_spotify_access_token(self):
        return cipher.decrypt(self.spotify_access_token).decode() if self.spotify_access_token else None

    def get_decrypted_spotify_refresh_token(self):
        return cipher.decrypt(self.spotify_refresh_token).decode() if self.spotify_refresh_token else None

    def is_spotify_token_expired(self):
        """Check if Spotify token is expired or will expire soon (within 5 minutes)"""
        if not self.spotify_token_expiration:
            return True
        return datetime.utcnow() + timedelta(minutes=5) >= self.spotify_token_expiration

    def refresh_spotify_token(self, client_id, client_secret):
        """Refresh Spotify access token using the refresh token"""
        current_app.logger.info(f"Starting token refresh for user {self.spotify_uri}")
        if not self.spotify_refresh_token:
            return False

        auth_header = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.get_decrypted_spotify_refresh_token()
        }

        response = requests.post(
            'https://accounts.spotify.com/api/token',
            headers=headers,
            data=data,
            timeout=15
        )

        if response.status_code == 200:
            current_app.logger.info(f"Token refresh successful for user {self.spotify_uri}")
            token_data = response.json()
            self.set_spotify_tokens(
                token_data['access_token'],
                token_data.get('refresh_token', self.get_decrypted_spotify_refresh_token()),
                token_data.get('expires_in', 3600)  # Default to 1 hour if not provided
            )
            return True
        current_app.logger.error(f"Token refresh failed for user {self.spotify_uri}: {response.status_code}")

        return False


class TwitchToken(db.Model):
    __tablename__ = 'twitch_tokens'
    id = db.Column(db.Integer, primary_key=True)   
    twitch_uri = db.Column(db.String(255), ForeignKey(User.twitch_uri))
    twitch_access_token = db.Column(db.LargeBinary, nullable=True)
    twitch_refresh_token = db.Column(db.LargeBinary, nullable=True)
    twitch_token_expiration = db.Column(db.DateTime, nullable=True)

    user = relationship("User")

    def set_twitch_tokens(self, user_id, access, refresh, expires_in):
        self.twitch_uri = user_id  # Don't encrypt this as it's a database column
        self.twitch_access_token = cipher.encrypt(access.encode())
        self.twitch_refresh_token = cipher.encrypt(refresh.encode())
        self.twitch_token_expiration = datetime.utcnow() + timedelta(seconds=expires_in)

    def get_decrypted_twitch_access_token(self):
        return cipher.decrypt(self.twitch_access_token).decode() if self.twitch_access_token else None

    def get_decrypted_twitch_refresh_token(self):
        return cipher.decrypt(self.twitch_refresh_token).decode() if self.twitch_refresh_token else None


    def is_twitch_token_expired(self):
        """Check if Twitch token is expired or will expire soon (within 5 minutes)"""
        if not self.twitch_token_expiration:
            return True
        return datetime.utcnow() + timedelta(minutes=5) >= self.twitch_token_expiration

    def refresh_twitch_token(self, client_id, client_secret):
        """Refresh Twitch access token using the refresh token"""
        if not self.twitch_refresh_token:
            return False

        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': self.get_decrypted_twitch_refresh_token()
        }

        response = requests.post(
            'https://id.twitch.tv/oauth2/token',
            data=data
        )

        if response.status_code == 200:
            token_data = response.json()
            print(f"Token data: {token_data}")
            # Get user info with new token to verify/update username
            user_response = requests.get(
                "https://api.twitch.tv/helix/users",
                headers={
                    'Authorization': f'Bearer {token_data["access_token"]}',
                    'Client-Id': client_id
                }
            )

            if user_response.status_code == 200:
                print(f"User Response: {user_response.json()}")
                user_data = user_response.json()['data'][0]
                twitch_user_id = user_data['id']
                twitch_login = user_data['login']

                # Set tokens and user info
                self.set_twitch_tokens(
                    twitch_user_id,
                    token_data['access_token'],
                    token_data['refresh_token'],
                    token_data.get('expires_in', 14400),  # Default to 4 hours if not provided
                )
                return True

            return False
        return False


class SongPlaying(db.Model):
    __tablename__ = "songs_playing"
    id = db.Column(db.Integer, primary_key=True)
    spotify_uri = db.Column(db.String(255), ForeignKey(User.spotify_uri))
    current_playing_song_id = db.Column(db.String(255), nullable=True)
    song_played_at = db.Column(db.DateTime, nullable=True)
    current_playing_song_title = db.Column(db.String(255), nullable=True)
    current_playing_song_artist = db.Column(db.String(255), nullable=True)
    current_playing_song_uri = db.Column(db.String(255), nullable=True)

    user = relationship("User")

    def update_current_playing_song(self, song_id, title, artist, uri):
        self.current_playing_song_id = song_id
        self.song_played_at = datetime.utcnow()
        self.current_playing_song_artist = artist
        self.current_playing_song_title = title
        self.current_playing_song_uri = uri
        db.session.commit()
