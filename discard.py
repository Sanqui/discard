import os
import logging
import datetime
import json
import traceback
import copy

import click
import discord
import vcr


#logging.basicConfig(level=logging.DEBUG)
class StreamingCassette(vcr.cassette.Cassette):
    '''
        Subclass of the VCR Cassette which streams output instead
        of writing it all at once, and supports swapping output files
        at runtime.

        VCR was not exactly built for this, but we can make it happen.
    '''
    pass
    def __init__(self, path, filename, **kwargs):
        super().__init__(None, **kwargs)
        self.path = path
        self.file = None
        self.num_requests = 0

        self.switch_file(filename)
    
    def switch_file(self, filename):
        if self.file != None:
            self.file.close()

        self.file = open(self.path + filename, 'w')
        self.dirty = False
        self.rewound = True
    
    def append(self, request, response):
        """Add a request, response pair to this cassette"""
        request = self._before_record_request(request)
        if not request:
            return
        response = copy.deepcopy(response)
        response = self._before_record_response(response)
        if response is None:
            return
        
        if response["body"]["string"] is not None and isinstance(response["body"]["string"], bytes):
            response["body"]["string"] = response["body"]["string"].decode("utf-8")
        obj = {'request': request._to_dict(), 'response': response}
        json.dump(obj, self.file)
        self.file.write("\n")
        self.num_requests += 1
        self.dirty = True

    def _load(self):
        pass

    def _save(self, force=False):
        if self.file != None:
            self.file.close()


class DiscardClient(discord.Client):
    def __init__(self, *args, discard_logger=None, cassette=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.discard_logger = discard_logger
        self.cassette = cassette

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


class Discard():
    def __init__(self, token):
        self.token = token

    def start(self):
        self.datetime_start = datetime.datetime.now()
        self.datetime_end = None
        self.finished = False
        self.completed = False
        self.errors = False
        self.exception = None
        self.traceback = None
        self.requests = 0

        self.output_directory = f'out/{self.datetime_start}/'
        os.mkdir(self.output_directory)

        self.write_meta_file()
    
    def end(self):
        self.finished = True
        self.datetime_end = datetime.datetime.now()

        self.write_meta_file()

    def run(self):
        self.start()

        try:
            with StreamingCassette.use(path=self.output_directory, filename='meta.jsonl', record_mode='all') as cassette:
                self.client = DiscardClient(discard_logger=self, cassette=cassette)
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
            'requests': self.requests
        }

        with open(self.output_directory + 'run.meta.json', 'w') as f:
            json.dump(obj, f, indent=4)


@click.command()
@click.option('--token', required=True, help='Bot or user token.')
def main(token):
    #with vcr.use_cassette('fixtures/vcr_cassettes/test4.yaml'):
    discard = Discard(token=token)
    discard.run()

if __name__ == '__main__':
    main()
