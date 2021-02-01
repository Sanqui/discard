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

import discord


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

            self.discard.start_channel(channel)

            num_messages = 0
            newest_message = None
            oldest_message = None
            
            async for message in channel.history(limit=None):
                if newest_message == None:
                    newest_message = message
                # TODO capture reactions

                num_messages += 1
                
            oldest_message = message

            self.discard.end_channel(channel, num_messages, oldest_message, newest_message)
        else:
            raise ValueError(f"Unknown mode: {self.discard.mode}")

        # Quit
        await self.close()

    async def on_socket_raw_send(self, payload):
        self.discard.log_ws_send(payload)

    async def on_socket_response(self, msg):
        self.discard.log_ws_recv(msg)
    
    async def on_error(self, event_method, *args, **kwargs):
        # Reraising the exception doesn't close the connection,
        # so we save it and raise it outside.
        self.exception = sys.exc_info()
        await self.close()


class Discard():
    def __init__(self, token, mode, output_dir, command=None, channel_id=None, is_user_account=False, no_scrub=False):
        self.token = token
        self.mode = mode
        self.command = command
        self.channel_id = channel_id
        self.is_user_account = is_user_account
        self.no_scrub = no_scrub
        self.output_dir_root = output_dir
        self.client = None

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
        self.profile = None

        self.output_directory = self.output_dir_root + '/' + self.datetime_start.strftime('%Y%m%dT%H%M%S_'+self.mode)
        if os.path.exists(self.output_directory):
            self.output_directory += "_" + self.ident[0:5]
        if os.path.exists(self.output_directory):
            raise RuntimeError("Fatal: Run directory already exists")
        self.output_directory += "/"
        os.makedirs(self.output_directory)

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
            'ident': self.ident,
            'completed': self.completed,
            'finished': self.finished,
            'errors': self.errors,
            'exception': self.exception,
            'traceback': self.traceback,
            'num_http_requests': self.num_http_requests,
            'num_ws_packets': self.num_ws_packets,
            'profile': None
        }

        if self.client and self.client.user:
            obj['user'] = {
                'id': self.client.user.id,
                'name': self.client.user.name,
                'discriminator': self.client.user.discriminator,
                'bot': self.client.user.bot
            }

        with open(self.output_directory + 'run.meta.json', 'w') as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)
    
    def start_channel(self, channel):
        self.request_file.close()

        guild_id = channel.guild.id
        os.mkdir(self.output_directory + str(guild_id))
        self.request_file = open(self.output_directory + f'{guild_id}/{channel.id}.jsonl', 'w')
    
    def end_channel(self, channel, num_messages, oldest_message, newest_message):
        # This information is intentionally minimalistic. It's supposed to be
        # a human-readable summary, not a resource. Logged requests contain all data.
        obj = {
            'channel': {
                'id': channel.id,
                'name': channel.name,
                'type': str(channel.type)
            },
            'run': {
                'num_messages': num_messages,
                'oldest_message': None,
                'newest_message': None
            }
        }

        if oldest_message is not None:
            obj['run']['oldest_message'] = {
                'id': oldest_message.id,
                'timestamp': oldest_message.created_at.isoformat() # TODO these need to be converted to UTC!
            }
        if newest_message is not None:
            obj['run']['newest_message'] = {
                'id': newest_message.id,
                'timestamp': newest_message.created_at.isoformat()
            }

        with open(self.output_directory + f'{channel.guild.id}/{channel.id}.meta.json', 'w') as f:
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