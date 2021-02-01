from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport
import time
from jwt import encode
from os import getenv


class GQLService:
    @staticmethod
    def make_token():
        secret = getenv("GQL_ACCOUNT_SECRET")
        message = {
            "exp": int(time.time()) + (60 * 60 * 24 * 5),
            "scopes": "read:users write:users",
        }
        return encode(message, secret, algorithm='HS256')

    @staticmethod
    def make_query(query, with_fragments=True):
        if not with_fragments:
            return gql(query)

        fragments = """
            fragment UserSubscriptionInformation on AccountSubscriptionUser {
              id
              username
              picture
              name
              discordId
              pronoun
              roles {
                id
                name
              }
              badges {
                id
                displayed
                order
                details {
                  emoji
                }
              }
              bio
            }
                """
        return gql(query + "\n" + fragments)

    @staticmethod
    async def query_http(query, variable_values=None, with_fragments=True):
        transport = AIOHTTPTransport(
            # url="https://graph.codeday.org/",
            url="http://localhost:4000/",
            headers={"authorization": f"Bearer {GQLService.make_token()}"})
        client = Client(transport=transport, fetch_schema_from_transport=True)
        return await client.execute_async(GQLService.make_query(query, with_fragments=with_fragments),
                                          variable_values=variable_values)

    @staticmethod
    async def subscribe_ws(query, variable_values=None, with_fragments=True):
        token = GQLService.make_token()
        transport = WebsocketsTransport(
            url='ws://graph.codeday.org/subscriptions',
            init_payload={'authorization': 'Bearer ' + token}
        )
        session = Client(transport=transport, fetch_schema_from_transport=True)
        async for result in session.subscribe_async(GQLService.make_query(query, with_fragments=with_fragments),
                                                    variable_values=variable_values):
            yield result

    @staticmethod
    async def get_user_from_discord_id(discord_id):
        query = """
            query getUserFromDiscordId($id: String!) {
              account {
                getUser(where: {discordId: $id}, fresh: true) {
                  id
                  username
                  picture
                  name
                  discordId
                  pronoun
                  roles {
                    id
                    name
                  }
                  badges {
                    id
                    displayed
                    order
                    details {
                      emoji
                    }
                  }
                  bio
                }
              }
            }
        """
        params = {"id": str(discord_id)}
        result = await GQLService.query_http(query, variable_values=params, with_fragments=False)
        return result["account"]["getUser"]

    @staticmethod
    async def get_user_from_user_id(id):
        query = """
            query getUserFromUsername($id: ID!) {
              account {
                getUser(where: {id: $id}, fresh: true) {
                  id
                  username
                  picture
                  name
                  discordId
                  pronoun
                  roles {
                    id
                    name
                  }
                  badges {
                    id
                    displayed
                    order
                    details {
                      emoji
                    }
                  }
                  bio
                }
              }
            }
        """
        params = {"id": str(id)}
        result = await GQLService.query_http(query, variable_values=params, with_fragments=False)
        return result["account"]["getUser"]

    @staticmethod
    async def link_discord(user_id, discord_id):
        mutation = """
            mutation linkDiscord ($userId: ID!, $discordId: String!) {
              account {
                linkDiscord(userId: $userId, discordId: $discordId)
              }
            }
        """
        params = {"userId": user_id, "discordId": str(discord_id)}
        result = await GQLService.query_http(mutation, variable_values=params, with_fragments=False)
        return result