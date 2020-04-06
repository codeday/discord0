from functools import wraps
import os
import requests
from flask import render_template
from flask import session
from flask import Flask, redirect, url_for
from flask_discord import DiscordOAuth2Session
from auth0.v3.management import Auth0
from auth0.v3.authentication import GetToken
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode

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
    return redirect(url_for(".dashboard"))


@app.route('/login_auth0')
def login_auth0():
    return auth0.authorize_redirect(redirect_uri=os.getenv('CALLBACK_URL'))


def requires_auth0(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'profile' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated


@app.route('/dashboard')
@requires_auth0
def dashboard():
    print(session)
    return render_template('dashboard.html',
                           userinfo=session['jwt_payload'],
                           discord=discord)


@app.route('/bind')
def bind():
    domain = os.getenv('AUTH_DOMAIN')
    client_id = os.getenv('AUTH_CLIENT_ID')
    client_secret = os.getenv('AUTH_CLIENT_SECRET')
    get_token = GetToken(domain)
    token = get_token.client_credentials(client_id,
                                         client_secret, 'https://{}/api/v2/'.format(domain))['access_token']
    mgmt = Auth0(domain, token)
    mgmt.users.update(session['profile']['user_id'], {'user_metadata': {'discord_id': str(discord.fetch_user().id)}})

@app.route('/logout_auth0')
def logout_auth0():
    # Clear session stored data
    session.clear()
    # Redirect user to logout endpoint
    params = {'returnTo': url_for('dashboard', _external=True), 'client_id': os.getenv('AUTH_CLIENT_ID')}
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))