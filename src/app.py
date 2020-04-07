import os

from auth0.v3.authentication import GetToken
from auth0.v3.management import Auth0
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, session
from flask_discord import DiscordOAuth2Session
from werkzeug.middleware.proxy_fix import ProxyFix

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
    if 'profile' not in session:
        return redirect('login_auth0')
    if not discord.authorized:
        return redirect('login_discord')
    domain = os.getenv('AUTH_DOMAIN')
    client_id = os.getenv('AUTH_CLIENT_ID')
    client_secret = os.getenv('AUTH_CLIENT_SECRET')
    get_token = GetToken(domain)
    token = get_token.client_credentials(client_id,
                                         client_secret, 'https://{}/api/v2/'.format(domain))['access_token']
    mgmt = Auth0(domain, token)
    mgmt.users.update(session['profile']['user_id'], {'user_metadata': {'discord_id': str(discord.fetch_user().id)}})
    out = f"{session['profile']['name']}'s CodeDay account has been successfully associated with the Discord account \
{discord.fetch_user().username}#{discord.fetch_user().discriminator}! \n\
Please close this window"
    session.clear()
    return out


app = ProxyFix(app, x_for=1, x_host=1)
