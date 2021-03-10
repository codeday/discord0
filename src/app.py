import asyncio
import os
import sys
from threading import Thread
from time import sleep

from authlib.integrations.flask_client import OAuth
from discord_webhook import DiscordWebhook
from flask import Flask, redirect, session, request, make_response
from flask_discord import DiscordOAuth2Session
from raygun4py import raygunprovider
from werkzeug.middleware.proxy_fix import ProxyFix

from services.gqlservice import GQLService

webhookurl = os.getenv('DISCORD_WEBHOOK')


def handle_exception(exc_type, exc_value, exc_traceback):
    cl = raygunprovider.RaygunSender(os.getenv("RAYGUN_TOKEN"))
    cl.send_exception(exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'VERYSECRETMUCHWOW')
app.config["DISCORD_CLIENT_ID"] = os.getenv('DISCORD_CLIENT_ID')
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
oauth = OAuth(app)

discord = DiscordOAuth2Session(app)

auth0 = oauth.register(
    'auth0',
    client_id=os.getenv('AUTH_CLIENT_ID'),
    client_secret=os.getenv('AUTH_CLIENT_SECRET'),
    api_base_url=os.getenv('AUTH_API_BASE_URL'),
    access_token_url=os.getenv('AUTH_ACCESS_TOKEN_URL'),
    authorize_url=os.getenv('AUTH_AUTHORIZE_URL'),
    client_kwargs={
        'scope': 'openid profile email',
    },
)


@app.route('/callback_auth0')
def callback_auth():
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    # Store the user information in flask session.
    session['jwt_payload'] = userinfo
    session['profile'] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'picture': userinfo['picture']
    }
    return redirect('/')


@app.route("/login_discord")
def login_discord():
    return discord.create_session(scope=['identify'])


@app.route('/callback_discord')
def callback_discord():
    discord.callback()
    return redirect('/')


@app.route('/login_auth0')
def login_auth0():
    return auth0.authorize_redirect(redirect_uri=os.getenv('CALLBACK_URL'))


@app.route('/')
def bind():
    out = "An unhandled error occurred linking your accounts. Please contact a staff member so we can resolve " \
          "the issue."
    if 'profile' not in session:
        return redirect('login_auth0')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    user_check = loop.run_until_complete(GQLService.get_user_from_user_id(session['profile']['user_id']))

    # if GraphQL doesn't find an account for some reason
    if not user_check:
        loop.close()
        session.clear()
        return out

    # if CodeDay account is already linked to a Discord account
    if user_check["discordId"]:
        loop.close()
        session.clear()
        return redirect('https://www.codeday.org/help/article/1N8IBXVNNojWtfiJf6QvX3')

    # if user hasn't logged into discord
    if not discord.authorized:
        loop.close()
        return redirect('login_discord')

    discord_check = loop.run_until_complete(GQLService.get_user_from_discord_id(discord.fetch_user().id))

    # if Discord account is already linked to a CodeDay account
    if discord_check and "id" in discord_check:
        session.clear()
        loop.close()
        return redirect('https://www.codeday.org/help/article/1N8IBXVNNojWtfiJf6QvX3')

    link_discord = loop.run_until_complete(
        GQLService.link_discord(session['profile']['user_id'], discord.fetch_user().id))

    # if GraphQL links Discord account successfully
    if link_discord:
        out = f"{session['profile']['name']}'s CodeDay account has been successfully associated with the Discord account \
                {discord.fetch_user().username}#{discord.fetch_user().discriminator}! \n\
                Please close this window."

    loop.close()
    session.clear()
    return out


def async_update(data):
    webhook = DiscordWebhook(url=webhookurl,
                             content=f"a~update <@{data['response']['body']['user_metadata']['discord_id']}>")
    response = webhook.execute()
    while not response.ok:
        if response.status_code == 429:
            sleep(1)
            response = webhook.execute()
        else:
            print(response)


@app.route('/update_hook', methods=['POST'])
def update_hook():
    data = request.json
    Thread(target=async_update, args=tuple([data])).start()
    return make_response("OK", 200)


app = ProxyFix(app, x_for=1, x_host=1)
