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
        print(f'We have logged in as {self.user.name} (id {self.user.id})')

        # Fetch self using a the HTTP API
        user = await self.fetch_user(self.user.id)
        print(f"Fetched user: {user}")

        # Quit
        await self.close()

    async def on_socket_raw_send(self, payload):
        self.discard.log_ws_send(payload)

    async def on_socket_response(self, msg):
        self.discard.log_ws_recv(msg)


class Discard():
    def __init__(self, token):
        self.token = token

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

        self.request_file = open(self.output_directory + 'meta.jsonl', 'w')
    
    def end(self):
        self.request_file.close()

        self.finished = True
        self.datetime_end = datetime.datetime.now(datetime.timezone.utc)

        self.write_meta_file()

    def run(self):
        self.start()

        try:
            self.client = DiscardClient(discard=self)
            self.client.run(self.token)
        except Exception as ex:
            self.errors = True
            self.exception = type(ex).__name__ + f"({ex})"
            self.traceback = traceback.format_exc()
            self.end()
            raise
        
        self.completed = True
        self.end()
    
    def write_meta_file(self):
        obj = {
            'client': {
                'name': 'discard',
                'version': '0.0.0'
            },
            'command': 'TODO',
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


@click.command()
@click.option('--token', required=True, help='Bot or user token.')
def main(token):
    #with vcr.use_cassette('fixtures/vcr_cassettes/test4.yaml'):
    discard = Discard(token=token)
    discard.run()

if __name__ == '__main__':
    main()
