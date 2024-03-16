# -*- coding: utf-8 -*-
"""The app module, containing the app factory function."""
import logging
import sys
import pytz
import asyncio
import disnake
from disnake.ext import commands as disnake_commands
import threading
import os
from datetime import datetime, timezone

from flask import Flask, render_template

from alarm_demo import commands, public, user
from alarm_demo.extensions import (
    bcrypt,
    cache,
    csrf_protect,
    db,
    debug_toolbar,
    flask_static_digest,
    login_manager,
    migrate,
)

intents = disnake.Intents.default()
intents.message_content = True

bot = disnake_commands.Bot(command_prefix='!', intents=intents)
discord_key = os.environ.get('DISCORD_TOKEN')
channel_id = 1216752605078749287

@bot.event
async def on_ready():
    asyncio.create_task(alarm_task())  # Start the alarm task
    print(f'Logged in as {bot.user}')
    
    
@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

def run_bot():
    bot.run(discord_key)

@bot.slash_command(description="List available commands")
async def help(inter):
    await inter.response.send_message("""
    ```
    - /alarm: Immediately triggers the alarm.
    - /save-timezone: Saves the time zone
    - /alarm-set: Sets the alarm for the timezone saved.
    - /alarm-set-explicit <HH:MM> <Timezone>: Sets the alarm for a specific time. Timezone should be in TZ identifier format (e.g., Europe/Berlin).
    - /toggle: Toggles the alarm on or off without resetting the set time.
    - /time: Checks the current time of a TZ identified time zone
    - /countdown: Shows the remaining time until the alarm goes off.
    ``` To find your TZ identifier for `/alarm set` visit: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    """)

@bot.slash_command(description="Get the current time in a specified timezone")
async def time(inter, timezone: str):
    try:
        # Attempt to fetch the timezone from the pytz library
        tz = pytz.timezone(timezone)
        # Get the current time in the specified timezone
        now = datetime.now(tz)
        # Format the time string
        time_str = now.strftime('%Y-%m-%d %H:%M:%S')
        await inter.response.send_message(f"The current time in {timezone} is: {time_str}")
    except pytz.UnknownTimeZoneError:
        await inter.response.send_message(f"Unknown timezone: '{timezone}'. Please enter a valid IANA timezone.")

@bot.slash_command(description="Trigger the alarm immediately")
async def alarm(inter):
    global alarm_active, alarm_time
    # Code to immediately trigger the alarm
    if alarm_active and alarm_time:
        await inter.response.send_message("@everyone Alarm triggered!")
        finish()
    if not alarm_time:
        await inter.response.send_message("Alarm is not set!")
    if not alarm_active: 
        await inter.response.send_message("Alarm is not active!")

@bot.slash_command(description="Set the alarm according to explicit timezone accurately considering the date")
async def alarm_set_explicit(inter, time: str, timezone: str):
    global alarm_time, alarm_active, active_timezone
    try:
        user_timezone = pytz.timezone(timezone)
        # Now correctly considering the user's timezone for today's date
        today_user_tz = datetime.now(user_timezone).date()
        naive_user_datetime = datetime.strptime(f"{today_user_tz} {time}", "%Y-%m-%d %H:%M")
        user_datetime = user_timezone.localize(naive_user_datetime, is_dst=None)
        alarm_time = user_datetime.astimezone(pytz.utc)
        alarm_active = True
        active_timezone = user_timezone
        await inter.response.send_message(f"Alarm set for {time} {timezone} correctly considering the date. UTC Time: {alarm_time}")
    except Exception as e:
        await inter.response.send_message(f"Error setting alarm: {str(e)}")


@bot.slash_command(description="Save timezone")
async def save_timezone(inter, timezone: str):
    global saved_timezone
    try:
        pytz.timezone(timezone)  # Check if the timez1216752605078749287one is valid
        saved_timezone = pytz.timezone(timezone)
        await inter.response.send_message(f"Timezone set to {timezone}.")
    except pytz.UnknownTimeZoneError:
        await inter.response.send_message(f"Error: Unknown timezone '{timezone}'. You can find your TZ identifier here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")

@bot.slash_command(description="Set alarm according to saved timezone considering the date")
async def alarm_set(inter, time: str):
    global alarm_time, alarm_active, active_timezone, saved_timezone
    if not saved_timezone:
        await inter.response.send_message("You need to save a timezone first!")
    else:
        try:
            # Now correctly considering the saved timezone for today's date
            today_saved_tz = datetime.now(saved_timezone).date()
            naive_user_datetime = datetime.strptime(f"{today_saved_tz} {time}", "%Y-%m-%d %H:%M")
            user_datetime = saved_timezone.localize(naive_user_datetime, is_dst=None)
            alarm_time = user_datetime.astimezone(pytz.utc)
            alarm_active = True
            active_timezone = saved_timezone
            await inter.response.send_message(f"Alarm set for {time} considering the saved timezone date. UTC Time: {alarm_time}")
        except Exception as e:
            await inter.response.send_message(f"Error setting alarm: {str(e)}")

    
@bot.slash_command(description="Toggle the alarm on or off")
async def toggle(inter):
    global alarm_active
    alarm_active = not alarm_active
    status = "ON" if alarm_active else "OFF"
    await inter.response.send_message(f"Alarm notifications are toggled: {status}.")

@bot.slash_command(description="Show countdown to the alarm")
async def countdown(inter):
    global alarm_time, active_timezone
    if alarm_time:
        if active_timezone is not None:
            now = datetime.now(pytz.utc).astimezone(active_timezone)
        else:
            now = datetime.now(pytz.utc)
        
        delta = alarm_time - now
        if delta.total_seconds() > 0:
            # Format delta for readability
            seconds = delta.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            countdown_message = f"Alarm will ring in {hours} hours, {minutes} minutes, and {seconds} seconds."
            await inter.response.send_message(countdown_message)
        else:
            await inter.response.send_message("The alarm time has passed.")
    else:
        await inter.response.send_message("No alarm is set.")
        
@bot.slash_command(description="List all available time zone codes")
async def tz(inter):
    await inter.response.send_message("You can find your TZ identifier here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones")

# Alarm state
alarm_time = None
alarm_active = True
active_timezone = None
saved_timezone = None

def finish():
    global alarm_time, alarm_active
    alarm_time = None
    alarm_active = False
    active_timezone = None


async def alarm_task():
    global alarm_time, alarm_active
    while True:
        await asyncio.sleep(1)  # Corrected to check every minute
        if alarm_time and alarm_active:
            now_utc = datetime.now(pytz.utc)
            if now_utc >= alarm_time:
                channel = bot.get_channel(channel_id)
                if channel:
                    finish()
                    await channel.send("@everyone Alarm triggered!")
                    # After triggering the alarm, reset alarm_time and alarm_active

run_bot()

def create_app(config_object="alarm_demo.settings"):
    """Create application factory, as explained here: http://flask.pocoo.org/docs/patterns/appfactories/.

    :param config_object: The configuration object to use.
    """
    app = Flask(__name__.split(".")[0])
    app.config.from_object(config_object)
    register_extensions(app)
    register_blueprints(app)
    register_errorhandlers(app)
    register_shellcontext(app)
    register_commands(app)
    configure_logger(app)
    return app


def register_extensions(app):
    """Register Flask extensions."""
    bcrypt.init_app(app)
    cache.init_app(app)
    db.init_app(app)
    csrf_protect.init_app(app)
    login_manager.init_app(app)
    debug_toolbar.init_app(app)
    migrate.init_app(app, db)
    flask_static_digest.init_app(app)
    return None


def register_blueprints(app):
    """Register Flask blueprints."""
    app.register_blueprint(public.views.blueprint)
    app.register_blueprint(user.views.blueprint)
    return None


def register_errorhandlers(app):
    """Register error handlers."""

    def render_error(error):
        """Render error template."""
        # If a HTTPException, pull the `code` attribute; default to 500
        error_code = getattr(error, "code", 500)
        return render_template(f"{error_code}.html"), error_code

    for errcode in [401, 404, 500]:
        app.errorhandler(errcode)(render_error)
    return None


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"db": db, "User": user.models.User}

    app.shell_context_processor(shell_context)


def register_commands(app):
    """Register Click commands."""
    app.cli.add_command(commands.test)
    app.cli.add_command(commands.lint)


def configure_logger(app):
    """Configure loggers."""
    handler = logging.StreamHandler(sys.stdout)
    if not app.logger.handlers:
        app.logger.addHandler(handler)
        
if __name__ == '__main__':
    t1 = threading.Thread(target=run_bot)
    t2 = threading.Thread(target=lambda: create_app().run())  # Assuming you have a create_app function.
    t1.start()
    t2.start()