from flask import Blueprint, jsonify, request, redirect, session, url_for, current_app, render_template, flash
from app.models import db, SpotifyTokens
from app.config import Config
from app.extensions import scheduler
import requests
import base64
import os
from urllib.parse import urlencode

main = Blueprint('main', __name__)

def get_moderated_channels(access_token, client_id, user_id):
    """Get list of channels where the user is a moderator"""
    current_app.logger.info(f"Getting moderated channels for user ID {user_id}")
    url = f"https://api.twitch.tv/helix/moderation/channels"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Client-Id': client_id
    }
    
    params = {
        'user_id': user_id  # The ID of the user whose moderator channels we want to get
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()['data']
    return None

@main.route('/')
def home():
    spotify_logged_in = False
    twitch_logged_in = False
    spotify_username = None
    twitch_username = None
    user = None    
    # Check if user is logged into Spotify
    if 'user_uri' in session:
        user = SpotifyTokens.query.filter_by(user_uri=session['user_uri']).first()
        if user:
            spotify_logged_in = True
            spotify_username = user.twitch_user_login
            if user.twitch_access_token:  # Check if user has Twitch token
                twitch_logged_in = True
                twitch_username = user.twitch_user_login

    return render_template('home.html', 
                         spotify_logged_in=spotify_logged_in,
                         twitch_logged_in=twitch_logged_in,
                           spotify_username=spotify_username,
                           twitch_username=twitch_username,
                           user=user)

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
    if 'user_uri' in session:
        user = SpotifyTokens.query.filter_by(user_uri=session['user_uri']).first()
        if user:
            db.session.delete(user)
            db.session.commit()
        session.pop('user_uri', None)
    
    auth_url = f'https://accounts.spotify.com/authorize?{urlencode(auth_params)}'
    return redirect(auth_url)

@main.route('/callback')
def callback():
    code = request.args.get('code')
    token_url = "https://accounts.spotify.com/api/token"
    auth_header = base64.b64encode(f"{Config.SPOTIFY_CLIENT_ID}:{Config.SPOTIFY_CLIENT_SECRET}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_header}'
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.SPOTIFY_REDIRECT_URI
    }
    response = requests.post(token_url, headers=headers, data=data)
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
        me_response = requests.get(me_url, headers=me_headers)
        me_data = me_response.json()
        user_id = me_data.get('id')
        current_app.logger.info("Retrieved user_id:", user_id)
        user_uri = me_data.get('uri')

        if user_uri:
            get_user = SpotifyTokens.query.filter_by(user_uri=user_uri).first()
            if get_user:
                get_user.set_spotify_tokens(access_token, refresh_token, expires_in)
            else:
                user_token = SpotifyTokens(user_id=user_id, user_uri=user_uri)
                user_token.set_spotify_tokens(access_token, refresh_token, expires_in)
                db.session.add(user_token)
        db.session.commit()
        session['user_uri'] = user_uri
        return redirect(url_for('main.home'))
    else:
        return jsonify({'error': 'Failed to obtain token'}), 400

@main.route('/logout')
def logout():
    if 'user_uri' in session:
        # Get the user from database
        user = SpotifyTokens.query.filter_by(user_uri=session['user_uri']).first()
        if user:
            # Delete the user from database
            db.session.delete(user)
            db.session.commit()
    
    # Clear the session
    session.clear()
    return redirect(url_for('main.home'))

@main.route('/twitch_login')
def twitch_login():
    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize?response_type=code"
        f"&client_id={Config.TWITCH_CLIENT_ID}&scope={Config.TWITCH_SCOPES}&redirect_uri={Config.TWITCH_REDIRECT_URI}"
    )
    return redirect(auth_url)

@main.route('/twitch_callback')
def twitch_callback():
    code = request.args.get('code')
    user_uri = session.get('user_uri')  # Get Spotify user_uri from session
    
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
    
    response = requests.post(token_url, data=data)
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
        
        user_response = requests.get(user_url, headers=headers)
        user_data = user_response.json()
        
        if 'data' in user_data and len(user_data['data']) > 0:
            user_info = user_data['data'][0]
            twitch_user_id = user_info.get('id')
            user_name = user_info.get('login')
            
            
            # First try to find by Spotify user_uri (which we know exists)
            user_token = SpotifyTokens.query.filter_by(user_uri=user_uri).first()
            
            if user_token:
                # Update existing record with Twitch information
                user_token.set_twitch_tokens(twitch_user_id, access_token, refresh_token, expires_in, user_name)
            else:
                return jsonify({'error': 'Spotify user record not found'}), 400
            
            db.session.commit()
            
            session['twitch_access_token'] = access_token
            session['twitch_refresh_token'] = refresh_token
            return redirect(url_for('main.home')) 
        else:
            return jsonify({'error': 'Failed to obtain user information'}), 400
    else:
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
    if 'user_uri' not in session:
        return redirect(url_for('main.home'))

    user = SpotifyTokens.query.filter_by(user_uri=session['user_uri']).first()
    if not user or not user.twitch_access_token:
        return redirect(url_for('main.home'))

    own_channel = {
        'broadcaster_login': user.twitch_user_login,
        'broadcaster_name': user.twitch_user_login,
        'is_own_channel': True
    }

    access_token = user.get_decrypted_twitch_access_token()
    moderated_channels = get_moderated_channels(
        access_token,
        Config.TWITCH_CLIENT_ID,
        user.twitch_user_id
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

    return render_template('manage_channel.html', channels=channels, current_channel=user.twitch_monitored_channel)
