import os
import logging
import datetime
import json

import click
import discord
import vcr

#logging.basicConfig(level=logging.DEBUG)

class DiscardLogger():
    def __init__(self):
        pass

    def start(self):
        self.datetime_start = datetime.datetime.now()
        self.datetime_end = None
        self.completed = False
        self.errors = False
        self.exception = None
        self.requests = 0

        self.output_directory = f'out/{self.datetime_start}/'
        os.mkdir(self.output_directory)

        self.write_meta_file()
    
    def end(self):
        self.completed = True
        self.datetime_end = datetime.datetime.now()

        self.write_meta_file()
    
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
            'errors': self.errors,
            'exception': self.exception,
            'requests': self.requests
        }

        with open(self.output_directory + 'run.meta.json', 'w') as f:
            json.dump(obj, f, indent=4)


class DiscardClient(discord.Client):
    def __init__(self, *args, discard_logger=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.discard_logger = discard_logger

    async def on_ready(self):
        print(f'We have logged in as {self.user.name} (id {self.user.id})')

        # Fetch self using a the HTTP API
        user = await self.fetch_user(self.user.id)
        print(f"Fetched user: {user}")

        # Quit
        await self.close()

    async def on_socket_raw_send(self, payload):
        print(">>>", payload)

    async def on_socket_response(self, msg):
        print("<<<", msg)


@click.command()
@click.option('--token', required=True, help='Bot or user token.')
def main(token):
    #with vcr.use_cassette('fixtures/vcr_cassettes/test4.yaml'):
    logger = DiscardLogger()
    logger.start()

    client = DiscardClient(discard_logger=logger)
    client.run(token)
    
    logger.end()

if __name__ == '__main__':
    main()
