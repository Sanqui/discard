import sys
import os
import logging
import datetime
import datetime
import json
import traceback
import copy

import click
import discord
import vcr

#logging.basicConfig(level=logging.DEBUG)

class DiscardClient(discord.Client):
    def __init__(self, *args, discard=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.discard = discard
        self.is_user_account = self.discard.is_user_account
        self.exception = None

        # monkeypatch discord.py request function to log

        request_func = self.http.request

        async def request_func_wrapped(route, *, files=None, **kwargs):
            datetime_start = datetime.datetime.now(datetime.timezone.utc)

            response = await request_func(route, files=files, **kwargs) # XXX await?

            datetime_end = datetime.datetime.now(datetime.timezone.utc)

            discard.log_http_request(route, response, datetime_start, datetime_end)

            return response
        
        self.http.request = request_func_wrapped

    async def on_ready(self):
        if self.discard.mode == 'profile':
            print(f'We have logged in as {self.user.name} (id {self.user.id})')

            if not self.is_user_account:
                # Fetch self using the HTTP API (not supported for user accounts)
                user = await self.fetch_user(self.user.id)
                print(f"Fetched user: {user}")
            else:
                # Fetch own profile using the HTTP API (not supported for bot accounts)
                profile = await self.fetch_user_profile(self.user.id)
                print(f"Fetched profile: {profile}")

        elif self.discard.mode == 'channel':
            channel = self.get_channel(self.discard.channel_id)

            print(f"Got channel: {channel}")
        else:
            raise ValueError(f"Unknown mode: {self.discard.mode}")

        # Quit
        await self.close()

    async def on_socket_raw_send(self, payload):
        self.discard.log_ws_send(payload)

    async def on_socket_response(self, msg):
        self.discard.log_ws_recv(msg)
    
    async def on_error(self, event_method, *args, **kwargs):
        # reraising the exception doesn't close the connection, so
        # we save it and raise it outside.
        self.exception = sys.exc_info()
        await self.close()


class Discard():
    def __init__(self, token, mode, command=None, channel_id=None, is_user_account=False, no_scrub=False):
        self.token = token
        self.mode = mode
        self.command = command
        self.channel_id = channel_id
        self.is_user_account = is_user_account
        self.no_scrub = no_scrub

    def start(self):
        self.datetime_start = datetime.datetime.now(datetime.timezone.utc)
        self.datetime_end = None
        self.finished = False
        self.completed = False
        self.errors = False
        self.exception = None
        self.traceback = None
        self.num_requests = 0

        self.output_directory = f'out/{self.datetime_start}/'
        os.mkdir(self.output_directory)

        self.write_meta_file()

        self.request_file = open(self.output_directory + 'run.jsonl', 'w')
    
    def end(self):
        self.request_file.close()

        self.finished = True
        self.datetime_end = datetime.datetime.now(datetime.timezone.utc)

        self.write_meta_file()

    def run(self):
        self.start()

        try:
            self.client = DiscardClient(discard=self)
            self.client.run(self.token, bot=not self.is_user_account)
            if self.client.exception:
                t, v, tb = self.client.exception
                raise v.with_traceback(tb)
        except Exception as ex:
            self.errors = True
            self.exception = type(ex).__name__ + f"({ex})"
            self.traceback = traceback.format_exc()
            self.end()
            raise
        
        self.completed = True
        print("Completed")
        self.end()
    
    def write_meta_file(self):
        obj = {
            'client': {
                'name': 'discard',
                'version': '0.0.0'
            },
            'command': self.command,
            'mode': self.mode,
            'is_user_account': self.is_user_account,
            'datetime_start': self.datetime_start.isoformat(),
            'datetime_end': self.datetime_end.isoformat() if self.datetime_end else None,
            'completed': self.completed,
            'finished': self.finished,
            'errors': self.errors,
            'exception': self.exception,
            'traceback': self.traceback,
            'num_requests': self.num_requests
        }

        with open(self.output_directory + 'run.meta.json', 'w') as f:
            json.dump(obj, f, indent=4)
    
    def log_http_request(self, route, response, datetime_start, datetime_end):
        obj = {
            'type': 'http',
            'datetime_start': datetime_start.isoformat(),
            'datetime_end': datetime_end.isoformat(),
            'request': {
                'method': route.method,
                'url': route.url
            },
            'response': {
                'data': response
            }
        }
        json.dump(obj, self.request_file)
        self.request_file.write('\n')
        self.num_requests += 1
    
    def log_ws_send(self, data):
        obj = {
            'type': 'ws',
            'direction': 'send',
            'data': data
        }
        if not self.no_scrub and self.token in data:
            obj['data'] = data.replace(self.token, '[SCRUBBED]')
            obj['scrubbed'] = True
        json.dump(obj, self.request_file)
        self.request_file.write('\n')

    def log_ws_recv(self, data):
        obj = {
            'type': 'ws',
            'direction': 'recv',
            'data': data
        }
        json.dump(obj, self.request_file)
        self.request_file.write('\n')

@click.group()
@click.option('-t', '--token', required=True, help='Bot or user token.',
            envvar='DISCORD_TOKEN')
@click.option('-U', '--is-user-account', default=False, is_flag=True, help='Log in as a user account.')
@click.option('--no-scrub', default=False, is_flag=True, help='Do not scrub token from logged data.')
@click.pass_context
def cli(ctx, token, is_user_account, no_scrub):
    ctx.ensure_object(dict)

    ctx.obj['token'] = token
    ctx.obj['is_user_account'] = is_user_account
    ctx.obj['no_scrub'] = no_scrub
    ctx.obj['command'] = sys.argv

@cli.command(help="Only log in and fetch profile information.")
@click.pass_context
def profile(ctx, ):
    discard = Discard(mode="profile", **ctx.obj)
    discard.run()

@cli.command(help="Archive a single channel.")
@click.option('-c', '--channel', required=True, help='Channel ID.', type=int) # TODO multiple
@click.pass_context
def channel(ctx, channel):
    discard = Discard(mode="channel", channel_id=channel, **ctx.obj)
    discard.run()

if __name__ == '__main__':
    cli()
