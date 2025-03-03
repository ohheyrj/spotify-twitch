from twitchio.ext import commands
from flask import current_app
from app.models import SpotifyTokens
from app.extensions import active_bots
import asyncio
import threading


class TwitchBot(commands.Bot):
    def __init__(self, **kwargs):
        self.flask_app = kwargs.pop('flask_app', None)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.bot_user_id = kwargs.pop('user_id', None)
        self.bot_channel = kwargs.pop('channel', None)
        self.processed_messages = set()  # Track processed messages
        kwargs['loop'] = loop
        super().__init__(**kwargs)

    async def event_ready(self):
        print(f'Bot is ready | Connected to {self.bot_channel}')

    async def event_message(self, message):
        # Prevent duplicate message processing
        if message.echo or message.id in self.processed_messages:
            return
            
        if message.content.lower().startswith('!whatsplaying'):
            self.processed_messages.add(message.id)
            await self.handle_whatsplaying(message)
            # Clean up old message IDs periodically
            if len(self.processed_messages) > 1000:
                self.processed_messages.clear()

    async def handle_whatsplaying(self, message):
        try:
            with self.flask_app.app_context():
                user = SpotifyTokens.query.filter_by(user_id=self.bot_user_id).first()
                if not user:
                    await message.channel.send("Error: User not found")
                    return
                
                if user.current_playing_song_title and user.current_playing_song_artist and user.current_playing_song_uri:
                    spotify_url = f"https://open.spotify.com/track/{user.current_playing_song_uri.split(':')[-1]}"
                    response = f"Now playing: {user.current_playing_song_title} by {user.current_playing_song_artist} - {spotify_url}"
                    await message.channel.send(response)
                else:
                    await message.channel.send("No track currently playing")
        except Exception as e:
            print(f"Error handling !whatsplaying command: {str(e)}")
            await message.channel.send("Error getting current song information")


def run_bot(bot):
    try:
        bot.loop.run_until_complete(bot.start())
    except Exception as e:
        print(f"Error running bot: {str(e)}")
        import traceback
        traceback.print_exc()

def start_bot(user_id, channel, flask_app):
    try:
        if channel in active_bots:
            print(f"Bot already running for channel {channel}")
            return False

        with flask_app.app_context():
            user = SpotifyTokens.query.filter_by(user_id=user_id).first()
            if not user:
                print(f"No user found with ID {user_id}")
                return False
            
            access_token = user.get_decrypted_twitch_access_token()
            if not access_token:
                print(f"No access token found for user {user_id}")
                return False

        bot = TwitchBot(
            token=access_token,
            prefix='!',
            initial_channels=[channel],
            user_id=user_id,
            channel=channel,
            flask_app=flask_app
        )
        
        active_bots[channel] = bot
        
        bot_thread = threading.Thread(target=run_bot, args=(bot,))
        bot_thread.daemon = True
        bot_thread.start()
        
        print(f"Started bot for channel {channel}")
        return True
        
    except Exception as e:
        print(f"Error starting bot: {str(e)}")
        if channel in active_bots:
            del active_bots[channel]
        return False

def stop_bot(channel):
    if channel in active_bots:
        try:
            bot = active_bots[channel]
            asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
            del active_bots[channel]
            print(f"Stopped bot for channel {channel}")
            return True
        except Exception as e:
            print(f"Error stopping bot: {str(e)}")
            return False
    return False
