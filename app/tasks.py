from datetime import datetime
from app.extensions import db, scheduler, active_bots
from app.models import SpotifyTokens
from app.config import Config
import spotipy
from app.twitchbot import start_bot, stop_bot
import requests
import logging
import traceback

logger = logging.getLogger(__name__)


def refresh_all_tokens(app):  # Add app parameter
    with app.app_context():
        logger.info(f"Starting token refresh at {datetime.now()}")
        users = SpotifyTokens.query.all()
         
        for user in users:
            try:
                if user.is_spotify_token_expired():
                    success = user.refresh_spotify_token(
                        Config.SPOTIFY_CLIENT_ID,
                        Config.SPOTIFY_CLIENT_SECRET
                    )
                    if success:
                        logger.info(f"Refreshed Spotify token for user {user.user_id}")
                    else:
                        logger.error(f"Failed to refresh Spotify token for user {user.user_id}")

                if user.is_twitch_token_expired():
                    success = user.refresh_twitch_token(
                        Config.TWITCH_CLIENT_ID,
                        Config.TWITCH_CLIENT_SECRET
                    )
                    if success:
                        logger.info(f"Refreshed Twitch token for user {user.twitch_user_id}")
                    else:
                        logger.error(f"Failed to refresh Twitch token for user {user.twitch_user_id}")

                db.session.commit()
            except Exception as e:
                db.session.rollback()
                error_traceback = traceback.format_exc()
                logger.error(f"Error processing user {user.user_id}: {str(e)}")
                logger.error(f"Traceback: {error_traceback}") 
        logger.info(f"Completed token refresh at {datetime.now()}")

def check_current_songs(app):
    with app.app_context():
        logger.info(f"Starting current song check at {datetime.now()}")
        users = SpotifyTokens.query.all()
        
        for user in users:
            try:
                # Create Spotify client
                decrypted_token = user.get_decrypted_spotify_access_token()
                logger.info(f"Decrypted token for user {user.user_id}: {bool(decrypted_token)}")  # Just print if we have a token, not the token itself
                
                sp = spotipy.Spotify(auth=decrypted_token)
                
                # Get current playing track
                current_track = sp.current_user_playing_track()
                if current_track is not None and current_track['item'] is not None:
                    # Extract song ID
                    current_song_id = current_track['item']['id']
                    current_song_title = current_track['item']['name']
                    current_song_uri = current_track['item']['uri']
                    current_song_artist = current_track['item']['artists'][0]['name']
                    # Only update if the song has changed
                    if current_song_id != user.current_playing_song_id:
                        user.update_current_playing_song(current_song_id, current_song_title, current_song_artist, current_song_uri)
                        logger.info(f"Updated current song for user {user.user_id} to {current_song_id}. {current_song_title} by {current_song_artist}. Spotify URI {current_song_uri}")
                else:
                    logger.info(f"No song currently playing for user {user.user_id}")
                db.session.commit()
            except spotipy.exceptions.SpotifyException as e:
                logger.error(f"Spotify API error for user {user.user_id}: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                logger.error(f"Error details: {e.__dict__}")
                db.session.rollback()
            except Exception as e:
                logger.error(f"Error type: {type(e)}")
                logger.error(f"Error args: {e.args}")
                logger.error(f"Full error details: {repr(e)}")
                logger.error(f"Error processing user {user.user_id}: {str(e)}")
                db.session.rollback()               
                logger.info(f"Completed current song check at {datetime.now()}")

def check_stream_status(app):
    try:
        with app.app_context():
            users = SpotifyTokens.query.all()
            for user in users:
                try:
                    # Only check status if there's a monitored channel
                    if user.twitch_monitored_channel:
                        headers = {
                            'Authorization': f'Bearer {user.get_decrypted_twitch_access_token()}',
                            'Client-Id': Config.TWITCH_CLIENT_ID
                        }
                        
                        response = requests.get(
                            f"https://api.twitch.tv/helix/streams?user_login={user.twitch_monitored_channel}",
                            headers=headers
                        )
                        
                        data = response.json().get('data', [])
                        
                        # Stream is live and bot isn't running
                        if data and user.twitch_monitored_channel and user.twitch_monitored_channel not in active_bots:
                            logger.info(f"Stream is live for {user.twitch_monitored_channel}")
                            start_bot(user.user_id, user.twitch_monitored_channel, app)
                        
                        # Stream is offline and bot is running
                        elif not data and user.twitch_monitored_channel and user.twitch_monitored_channel in active_bots:
                            logger.info(f"Stream is offline for {user.twitch_monitored_channel}")
                            stop_bot(user.twitch_monitored_channel)
                            
                except Exception as e:
                    logger.error(f"Error checking stream for {user.twitch_monitored_channel}: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error in check_stream_status: {str(e)}")
        import traceback
        traceback.print_exc()

def init_scheduler(app):
    # Remove existing job if it exists
    try:
        scheduler.remove_job('refresh_tokens')
        scheduler.remove_job('update_song')
        scheduler.remove_job('check_streams')
    except:
        pass
        
    scheduler.add_job(
        id='refresh_tokens',
        func=refresh_all_tokens,
        args=[app],  # Pass the app instance as an argument
        trigger='interval',
        minutes=1
    )

    scheduler.add_job(
        id='update_song',
        func=check_current_songs,
        args=[app],
        trigger='interval',
        seconds=60
    )

    # Add the job
    scheduler.add_job(
        id='check_streams',
        func=check_stream_status,
        args=[app],
        trigger='interval',
        minutes=1,
        max_instances=1,
        coalesce=True
    )
