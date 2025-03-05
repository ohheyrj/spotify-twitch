import base64
import os
from urllib.parse import urlencode
from flask import (Blueprint, jsonify, request,
                   redirect, session, url_for, current_app, render_template, flash)
import requests
import spotipy
from app.models import TwitchToken, db, SpotifyToken, User, SongPlaying
from app.config import Config
from app.extensions import scheduler

main = Blueprint('main', __name__)

def get_moderated_channels(access_token, client_id, user_id):
    """Get list of channels where the user is a moderator"""
    current_app.logger.info(f"Getting moderated channels for user ID {user_id}")
    url = "https://api.twitch.tv/helix/moderation/channels"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': client_id
    }

    params = {
        'user_id': user_id  # The ID of the user whose moderator channels we want to get
    }

    response = requests.get(url, headers=headers, params=params, timeout=15)

    if response.status_code == 200:
        return response.json()['data']
    return None

def get_spotify_playlists(spotify_uri):
    token = SpotifyToken.query.filter_by(spotify_uri=spotify_uri).first()
    playlist_items = []
    if token:
        sp = spotipy.Spotify(auth=token.get_decrypted_spotify_access_token())
        
        offset = 0
        while True:
            current_playlists = sp.current_user_playlists(offset=offset)
            if not current_playlists['items']:  # If no more playlists, break
                break
                
            for playlist in current_playlists['items']:
                playlist_items.append({
                    'id': playlist['id'],
                    'name': playlist['name']
                })
                
            if len(playlist_items) >= current_playlists['total']:  # If we've got all playlists, break
                break
                
            offset += 50  # Spotify's limit is 50, so increment by 50
            
        return playlist_items
    return []

@main.route('/')
def home():
    spotify_logged_in = False
    twitch_logged_in = False
    spotify_username = None
    twitch_username = None
    user = None
    spotify_profile_picture = None
    twitch_profile_picture = None
    spotify_playlists = None
    # Check if user is logged into Spotify
    if 'spotify_uri' in session:
        user = User.query.filter_by(spotify_uri=session['spotify_uri']).first()
        if user:
            spotify_logged_in = True
            spotify_username = user.spotify_uri.split(':')[2]
            spotify_profile_picture = user.spotify_display_picture
            spotify_playlists = get_spotify_playlists(user.spotify_uri)
            if user.twitch_uri:  # Check if user has Twitch token
                twitch_logged_in = True
                twitch_username = user.twitch_display_name
                twitch_profile_picture = user.twitch_display_picture

    return render_template('home.html',
                            spotify_logged_in=spotify_logged_in,
                            twitch_logged_in=twitch_logged_in,
                            spotify_username=spotify_username,
                            twitch_username=twitch_username,
                            spotify_profile_picture=spotify_profile_picture,
                            twitch_profile_picture=twitch_profile_picture,
                            user=user,
                            spotify_playlists=spotify_playlists)

@main.route('/login')
def login():
    # Generate a random state
    state = base64.b64encode(os.urandom(32)).decode('utf-8')
    session['state'] = state

    # Force consent screen and include all scopes
    auth_params = {
        'client_id': Config.SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': Config.SPOTIFY_REDIRECT_URI,
        'state': state,
        'scope': Config.SPOTIFY_SCOPES,
        'show_dialog': 'true'  # Force consent screen
    }

    # Clear existing tokens if user is logged in
    if 'spotify_uri' in session:
        user = SpotifyToken.query.filter_by(spotify_uri=session['spotify_uri']).first()
        if user:
            db.session.delete(user)
            db.session.commit()
        session.pop('spotify_uri', None)

    auth_url = f'https://accounts.spotify.com/authorize?{urlencode(auth_params)}'
    return redirect(auth_url)

@main.route('/callback')
def callback():
    code = request.args.get('code')
    token_url = "https://accounts.spotify.com/api/token"
    auth_header = base64.b64encode(
        f"{Config.SPOTIFY_CLIENT_ID}:{Config.SPOTIFY_CLIENT_SECRET}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_header}'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.SPOTIFY_REDIRECT_URI
    }
    response = requests.post(token_url, headers=headers, data=data, timeout=15)
    response_data = response.json()
    if 'access_token' in response_data:
        access_token = response_data['access_token']
        refresh_token = response_data['refresh_token']
        expires_in = response_data.get('expires_in', 3600)

        # Store the granted scopes
        granted_scopes = response_data.get('scope', '').split(' ')
        required_scopes = Config.SPOTIFY_SCOPES.split(' ')

        # Verify all required scopes were granted
        if not all(scope in granted_scopes for scope in required_scopes):
            return jsonify({
                'error': 'Missing required scopes. Please authorize again.'
            }), 400

        me_url = "https://api.spotify.com/v1/me"
        me_headers = {
            'Authorization': f'Bearer {access_token}'
        }
        me_response = requests.get(me_url, headers=me_headers, timeout=15)
        me_data = me_response.json()
        user_id = me_data.get('id')
        current_app.logger.info(f"Retrieved user_id: {user_id}")
        user_uri = me_data.get('uri')
        display_name = me_data.get('display_name')
        display_picture_url = me_data.get('images')[0].get('url')

        if user_uri:
            user = User.query.filter_by(spotify_uri=user_uri).first()

            if not user:
                user = User(spotify_uri=user_uri, spotify_display_name=display_name, spotify_display_picture=display_picture_url)
                db.session.add(user)

            spotify_token = SpotifyToken.query.filter_by(spotify_uri=user_uri).first()
            if spotify_token:
                spotify_token.set_spotify_tokens(access_token, refresh_token, expires_in)
            else:
                spotify_token = SpotifyToken(spotify_uri=user_uri)
                spotify_token.set_spotify_tokens(access_token, refresh_token, expires_in)
                db.session.add(spotify_token)
        db.session.commit()
        session['spotify_uri'] = user_uri
        return redirect(url_for('main.home'))

    return jsonify({'error': 'Failed to obtain token'}), 400

@main.route('/logout')
def logout():
    try:
        if 'spotify_uri' in session:
            # First get the user and their URIs from the User table
            user = User.query.filter_by(spotify_uri=session['spotify_uri']).first()
            
            if user:
                spotify_uri = user.spotify_uri
                twitch_uri = user.twitch_uri
                
                # Delete songs_playing entries
                songs_playing = SongPlaying.query.filter_by(spotify_uri=spotify_uri).all()
                for song in songs_playing:
                    db.session.delete(song)
                
                # Delete Spotify token
                spotify_token = SpotifyToken.query.filter_by(spotify_uri=spotify_uri).first()
                if spotify_token:
                    db.session.delete(spotify_token)
                
                # Delete Twitch token
                twitch_token = TwitchToken.query.filter_by(twitch_uri=twitch_uri).first()
                if twitch_token:
                    db.session.delete(twitch_token)
                
                # Finally delete the user
                db.session.delete(user)
                
                # Commit all deletions
                db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during logout: {str(e)}")
    finally:
        # Clear the session
        session.clear()
        return redirect(url_for('main.home'))

@main.route('/twitch_login')
def twitch_login():
    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize?response_type=code"
            f"&client_id={Config.TWITCH_CLIENT_ID}&scope={Config.TWITCH_SCOPES}&redirect_uri={Config.TWITCH_REDIRECT_URI}" # pylint: disable=line-too-long
    )
    return redirect(auth_url)

@main.route('/twitch_callback')
def twitch_callback():
    code = request.args.get('code')
    user_uri = session.get('spotify_uri')  # Get Spotify user_uri from session

    if not user_uri:
        return jsonify({'error': 'Spotify authentication required'}), 400

    token_url = "https://id.twitch.tv/oauth2/token"
    data = {
        'client_id': Config.TWITCH_CLIENT_ID,
        'client_secret': Config.TWITCH_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': Config.TWITCH_REDIRECT_URI
    }

    response = requests.post(token_url, data=data, timeout=15)
    token_data = response.json()

    if 'access_token' in token_data:
        access_token = token_data['access_token']
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 14400)

        user_url = "https://api.twitch.tv/helix/users"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Client-Id': Config.TWITCH_CLIENT_ID
        }

        user_response = requests.get(user_url, headers=headers, timeout=15)
        user_data = user_response.json()

        if 'data' in user_data and len(user_data['data']) > 0:
            user_info = user_data['data'][0]
            twitch_user_id = user_info.get('id')
            user_name = user_info.get('login')
            twitch_display_name = user_info.get('display_name')
            twitch_display_picture = user_info.get('profile_image_url')

            # First try to find by Spotify user_uri (which we know exists)
            user_token = User.query.filter_by(spotify_uri=user_uri).first()

            if user_token:
                # Update existing record with Twitch information
                if not User.query.filter_by(twitch_uri=twitch_user_id).first():
                    user_token.twitch_uri = twitch_user_id
                    user_token.twitch_display_name = twitch_display_name
                    user_token.twitch_display_picture = twitch_display_picture
                    db.session.add(user_token)
                    db.session.commit()
                
                twitch_token = TwitchToken.query.filter_by(twitch_uri=twitch_user_id).first()
                if twitch_token: 
                    twitch_token.set_twitch_tokens(
                        twitch_user_id, access_token, refresh_token, expires_in, user_name)
                    db.session.add(twitch_token)
                    db.session.commit()
                else:
                    twitch_token = TwitchToken(twitch_uri=twitch_user_id)
                    twitch_token.set_twitch_tokens(
                        twitch_user_id, access_token, refresh_token, expires_in) 
                    db.session.add(twitch_token)
                    db.session.commit()
            else:
                return jsonify({'error': 'Spotify user record not found'}), 400

            db.session.commit()

            session['twitch_access_token'] = access_token
            session['twitch_refresh_token'] = refresh_token
            return redirect(url_for('main.home'))

        return jsonify({'error': 'Failed to obtain user information'}), 400
    return jsonify({'error': 'Failed to obtain Twitch tokens'}), 400

@main.route('/scheduler/status')
def scheduler_status():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'next_run': job.next_run_time,
            'trigger': str(job.trigger)
        })
    return jsonify({
        'running': scheduler.running,
        'jobs': jobs
    })


@main.route('/manage_channel', methods=['GET', 'POST'])
def manage_channel():
    if 'spotify_uri' not in session:
        return redirect(url_for('main.home'))

    user = User.query.filter_by(spotify_uri=session['spotify_uri']).first()
    if not user:
        return redirect(url_for('main.home'))

    twitch_token = TwitchToken.query.filter_by(twitch_uri=user.twitch_uri).first()
    own_channel = {
        'broadcaster_login': user.twitch_display_name,
        'broadcaster_name': user.twitch_display_name,
        'is_own_channel': True
    }

    access_token = twitch_token.get_decrypted_twitch_access_token()
    moderated_channels = get_moderated_channels(
        access_token,
        Config.TWITCH_CLIENT_ID,
        user.twitch_uri
    )

    if request.method == 'POST':
        selected_channel = request.form.get('selected_channel')
        if selected_channel:
            user.twitch_monitored_channel = selected_channel
            db.session.commit()
            flash('Monitored channel updated successfully!', 'success')
            return redirect(url_for('main.home'))

    channels = [own_channel]
    if moderated_channels:
        channels.extend([{
            'broadcaster_login': channel['broadcaster_login'],
            'broadcaster_name': channel['broadcaster_name'],
            'is_own_channel': False
        } for channel in moderated_channels])

    return render_template('manage_channel.html',
                           channels=channels,
                           current_channel=user.twitch_monitored_channel)


@main.route('/save-spotify-settings', methods=['POST'])
def save_spotify_settings():
    # Check if user is logged in via session
    if 'spotify_uri' not in session:
        flash('Please login first!', 'error')
        return redirect(url_for('main.home'))
    
    try:
        # Get form data
        add_to_playlist = request.form.get('spotify_add_to_playlist') == 'true'
        playlist_id = request.form.get('playlist_id') if add_to_playlist else None

        # Get current user using session
        user = User.query.filter_by(spotify_uri=session['spotify_uri']).first()
        
        if user:
            # Update user settings
            user.spotify_add_to_playlist = add_to_playlist
            user.spotify_playlist_id = playlist_id
            db.session.commit()
            
            flash('Spotify settings updated successfully!', 'success')
        else:
            flash('User not found!', 'error')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving settings: {str(e)}', 'error')
        
    return redirect(url_for('main.home'))
