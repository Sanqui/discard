import sys
import os
import logging
import datetime
import datetime
import json
import traceback
import copy
import random
import string
import gzip
import asyncio
from pathlib import Path

import discord

DISCARD_VERSION = "0.1.0"

class NotFoundError(Exception):
    pass


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

            discard.log_http_request(route, kwargs, response, datetime_start, datetime_end)

            return response
        
        self.http.request = request_func_wrapped
    
    # Override the default run method in order to preserve KeyboardInterrupt
    def run(self, *args, **kwargs):
        loop = self.loop

        try:
            loop.run_until_complete(self.start(*args, **kwargs))
        except KeyboardInterrupt:
            self.exception = sys.exc_info()
        finally:
            loop.close()

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

            if channel is None:
                raise NotFoundError(f"Channel not found: {self.discard.channel_id}")

            print(f"Got channel: {channel}")
            await self.archive_channel(channel)

        elif self.discard.mode == 'guild':
            guild = self.get_guild(self.discard.guild_id)

            if guild is None:
                raise NotFoundError(f"Guild not found: {self.discard.guild_id}")

            print(f"Got guild: {guild}")
            await self.archive_guild(guild)
        else:
            raise ValueError(f"Unknown mode: {self.discard.mode}")

        # Quit
        await self.close()
    
    async def archive_channel(self, channel: discord.abc.GuildChannel):
        self.discard.start_channel(channel)

        # XXX is it a good idea for userbots to do this?
        #await self.fetch_channel(channel.id)

        num_messages = 0
        newest_message = None
        message = None
        
        # before and after datetimes must be timezone-naive in UTC (why not timezone-aware UTC?)
        async for message in channel.history(after=self.discard.after, before=self.discard.before, limit=None,
                                                oldest_first=True):
            if newest_message == None:
                newest_message = message
            # TODO capture reactions

            num_messages += 1
            
        oldest_message = message

        self.discard.end_channel(channel, num_messages, oldest_message, newest_message)
    
    async def archive_guild(self, guild: discord.Guild):
        self.discard.start_guild(guild)

        # XXX is it a good idea for userbots to do this?
        await self.fetch_guild(guild.id)
        await guild.fetch_channels()

        num_channels = 0
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).read_messages:
                await self.archive_channel(channel)
                num_channels += 1
        
        self.discard.end_guild(guild, num_channels)
            

    async def on_socket_raw_send(self, payload):
        self.discard.log_ws_send(payload)

    async def on_socket_response(self, msg):
        self.discard.log_ws_recv(msg)
    
    async def on_error(self, event_method, *args, **kwargs):
        # Reraising the exception doesn't close the connection,
        # so we save it and raise it outside.

        # TODO some errors would be best logged but kept non-fatal to still
        # fetch the most data possible.
        # Have an option for that.

        self.exception = sys.exc_info()
        await self.close()


class Discard():
    def __init__(self, token, mode, output_dir, command=None, channel_id=None, guild_id=None,
                    is_user_account=False, no_scrub=False, before=None, after=None,
                    gzip=False):
        self.token = token
        self.mode = mode
        self.command = command
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.is_user_account = is_user_account
        self.no_scrub = no_scrub
        self.output_dir_root = output_dir
        self.client = None
        self.before = before
        self.after = after
        self.gzip = gzip

        self.client = DiscardClient(discard=self)

    def start(self):
        self.datetime_start = datetime.datetime.now(datetime.timezone.utc)
        self.ident = ''.join([random.choice(string.ascii_lowercase + string.digits) for i in range(24)])
        self.datetime_end = None
        self.finished = False
        self.completed = False
        self.errors = False
        self.exception = None
        self.traceback = None
        self.num_http_requests = 0
        self.num_ws_packets = 0
        self.num_messages = 0
        self.num_guild_messages = 0
        self.profile = None

        self.run_directory = self.datetime_start.strftime('%Y%m%dT%H%M%S_'+self.mode)
        self.output_directory = self.output_dir_root / Path(self.run_directory)
        if os.path.exists(self.output_directory):
            self.run_directory += "_" + self.ident[0:5]
            self.output_directory = self.output_dir_root / Path(self.run_directory)
        if os.path.exists(self.output_directory):
            raise RuntimeError("Fatal: Run directory already exists")
        os.makedirs(self.output_directory)

        self.write_meta_file()

        self.open_request_file('run.jsonl')
    
    def open_request_file(self, filepath):
        filepath = Path(filepath)
        if len(filepath.parts) > 1:
            os.makedirs(self.output_directory / filepath.parts[0], exist_ok=True)
        
        if self.gzip:
            filepath = filepath.with_name(filepath.name + '.gz')

        if os.path.exists(self.output_directory / filepath):
            raise RuntimeError("Request file already exists")
        
        open_func = gzip.open if self.gzip else open
        self.request_file = open_func(self.output_directory / filepath, 'wt')
    
    def end(self):
        self.request_file.close()

        self.finished = True
        self.datetime_end = datetime.datetime.now(datetime.timezone.utc)

        self.write_meta_file()

    def run(self):
        self.start()

        try:
            self.client.run(self.token, bot=not self.is_user_account)
            if self.client.exception:
                t, v, tb = self.client.exception
                raise v.with_traceback(tb)
        except BaseException as ex:
            self.errors = True
            self.exception = type(ex).__name__ + f": {ex}"
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
                'version': DISCARD_VERSION
            },
            'command': self.command,
            'settings': {
                'mode': self.mode,
                'token': self.token if self.no_scrub else None,
                'is_user_account': self.is_user_account,
                'output_dir': str(self.output_dir_root),
                'after': self.before.isoformat() if self.before else None,
                'before': self.after.isoformat() if self.after else None,
                'no_scrub': self.no_scrub,
                'gzip': self.gzip
            },
            'run': {
                'datetime_start': self.datetime_start.isoformat(),
                'datetime_end': self.datetime_end.isoformat() if self.datetime_end else None,
                'run_directory': self.run_directory,
                'ident': self.ident,
                'completed': self.completed,
                'finished': self.finished,
                'errors': self.errors,
                'exception': self.exception,
                'traceback': self.traceback,
            },
            'summary': {
                'num_http_requests': self.num_http_requests,
                'num_ws_packets': self.num_ws_packets,
                'num_messages': self.num_messages
            },
            'user': None
        }

        if self.client and self.client.user:
            obj['user'] = {
                'id': self.client.user.id,
                'name': self.client.user.name,
                'discriminator': self.client.user.discriminator,
                'bot': self.client.user.bot
            }

        with open(self.output_directory / Path('run.meta.json'), 'w') as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
    
    def start_channel(self, channel):
        self.request_file.close()

        self.num_guild_messages = 0

        guild_id = channel.guild.id
        self.open_request_file(f'{guild_id}/{channel.id}.jsonl')
    
    def end_channel(self, channel, num_messages, oldest_message, newest_message):
        # This information is intentionally minimalistic. It's supposed to be
        # a human-readable summary, not a resource. Logged requests contain all data.
        obj = {
            'channel': {
                'id': channel.id,
                'name': channel.name,
                'type': str(channel.type)
            },
            'summary': {
                'num_messages': num_messages,
                'oldest_message': None,
                'newest_message': None
            }
        }

        if oldest_message is not None:
            obj['summary']['oldest_message'] = {
                'id': oldest_message.id,
                'timestamp': oldest_message.created_at.isoformat() # TODO these need to be converted to UTC!
            }
        if newest_message is not None:
            obj['summary']['newest_message'] = {
                'id': newest_message.id,
                'timestamp': newest_message.created_at.isoformat()
            }

        with open(self.output_directory / Path(f'{channel.guild.id}/{channel.id}.meta.json'), 'w') as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
        
        self.num_messages += num_messages
        self.num_guild_messages += num_messages
    
    def start_guild(self, guild):
        self.request_file.close()

        self.open_request_file(f'{guild.id}/guild.jsonl')

    
    def end_guild(self, guild, num_channels):
        obj = {
            'guild': {
                'id': guild.id,
                'name': guild.name,
            },
            'summary': {
                'num_channels': num_channels,
                'num_messages': self.num_guild_messages
            }
        }
        
        with open(self.output_directory / Path(f'{guild.id}/guild.meta.json'), 'w') as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
    
    def log_http_request(self, route, kwargs, response, datetime_start, datetime_end):
        obj = {
            'type': 'http',
            'datetime_start': datetime_start.isoformat(),
            'datetime_end': datetime_end.isoformat(),
            'request': {
                'method': route.method,
                'url': route.url,
            },
            'response': {
                'data': response
            }
        }
        if 'params' in kwargs:
            obj['request']['params'] = kwargs['params']
        json.dump(obj, self.request_file, ensure_ascii=False)
        self.request_file.write('\n')
        self.num_http_requests += 1
    
    def log_ws_send(self, data):
        now = datetime.datetime.now()
        obj = {
            'type': 'ws',
            'datetime': now.isoformat(),
            'direction': 'send',
            'data': data,
        }
        if not self.no_scrub and self.token in data:
            obj['data'] = data.replace(self.token, '[SCRUBBED]')
            obj['scrubbed'] = True
        json.dump(obj, self.request_file, ensure_ascii=False)
        self.request_file.write('\n')
        self.num_ws_packets += 1

    def log_ws_recv(self, data):
        now = datetime.datetime.now()
        obj = {
            'type': 'ws',
            'datetime': now.isoformat(),
            'direction': 'recv',
            'data': data
        }
        json.dump(obj, self.request_file, ensure_ascii=False)
        self.request_file.write('\n')
        self.num_ws_packets += 1
