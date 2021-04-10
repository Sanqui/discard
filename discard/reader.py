import json
import os
import gzip
import itertools
import datetime
from collections import defaultdict
from pathlib import Path

import discord

def read_chat(path):
    meta = json.load(open(path + '.meta.json'))
    if 'channel' not in meta:
        raise ValueError("Not a channel log")

    channel_id = meta['channel']['id']
    channel_name = meta['channel']['name']

    print(f"Channel {channel_name} (id {channel_id})")

    # Create a crippled state
    # TODO implement our own
    state = discord.state.ConnectionState.__new__(discord.state.ConnectionState)
    state.max_messages = 1000
    state.http = None
    state.clear()

    # Mock a guild
    # TODO restore from run data
    guild = discord.Guild.__new__(discord.Guild)
    guild.id = 0
    guild._members = {}
    guild._roles = {}

    channel = discord.TextChannel(state=state, guild=guild, data={
        'id': channel_id,
        'type': 0,
        'name': channel_name,
        'parent_id': 0, 'position': 0
    })

    if os.path.exists(path + '.jsonl.gz'):
        file = gzip.open(path + '.jsonl.gz')
    else:
        file = open(path + '.jsonl')

    for line in file:
        line = json.loads(line)
        if line['type'] != 'http':
            continue

        if line['request']['url'].endswith(f'/channels/{channel_id}/messages'):
            for message_data in reversed(line['response']['data']):
                message = discord.Message(state=state, channel=channel, data=message_data)
                if message.type == discord.MessageType.default:
                    print(f"[{message.created_at}] <{message.author}> {message.content}")
                else:
                    print(f"[{message.created_at}] {message.system_content}")

class Summarize():
    def __init__(self):
        # TODO coverage
        self.guilds = defaultdict(dict)
        self.num_runs = 0
    
    def parse_directory(self, path):
        self.now = datetime.datetime.now()

        directory = os.listdir(path)
        if 'run.meta.json' in directory:
            self.parse_run(path)
        else:
            for subdirectory in directory:
                if not os.path.isfile(path / subdirectory):
                    self.parse_directory(path / subdirectory)
        
        self.calculate_gaps()
    
    def parse_run(self, path):
        meta = json.load(open(path / 'run.meta.json'))

        if meta['settings']['mode'] != 'guild':
            # TODO
            return
        
        if not meta['run']['completed'] or not meta['run']['finished'] or meta['run']['errors']:
            print(f"Warning: Run not completed or has errors, skipping: {path}")
            return

        self.num_runs += 1

        if meta['client']['version'] < '0.3.3':
            # stupid bug
            meta['settings']['after'], meta['settings']['before'] = meta['settings']['before'], meta['settings']['after']

        run_after = meta['settings']['after'] or '0000-00-00T00:00:00'
        run_before = meta['settings']['before'] or meta['run']['datetime_start']
        
        for subdirectory in os.listdir(path):
            if not os.path.isfile(path / subdirectory):
                guild_meta = json.load(open(path / subdirectory / 'guild.meta.json'))
                guild_id = guild_meta['guild']['id']
                self.guilds[guild_id]['name'] = guild_meta['guild']['name']
                if 'channels' not in self.guilds[guild_id]:
                    self.guilds[guild_id]['channels'] = defaultdict(dict)
                
                for subfile in os.listdir(path / subdirectory):
                    if subfile.startswith('guild'):
                        continue
                    if subfile.endswith('.meta.json'):
                        channel_meta = json.load(open(path / subdirectory / subfile))
                        channel_id = channel_meta['channel']['id']
                        channel = self.guilds[guild_id]['channels'][channel_id]
                        channel['name'] = channel_meta['channel']['name']
                        if 'runs' not in channel:
                            channel['runs'] = []
                        channel['runs'].append((run_after, run_before))
                        self.guilds[guild_id]['channels'][channel_id] = channel

    def calculate_gaps(self):
        self.gaps = defaultdict(list)
        for guild_id, guild in self.guilds.items():
            for channel_id, channel in guild['channels'].items():
                channel_beginning = '0000-00-00T00:00:00' # discord.Object(channel_id).created_at.isoformat()
                end = datetime.datetime.utcnow().isoformat()

                ranges = []
                # union of ranges
                for after, before in sorted(channel['runs']):
                    if ranges and ranges[-1][1] >= after:
                        ranges[-1][1] = max(ranges[-1][1], before)
                    else:
                        ranges.append([after, before])
                
                flat = itertools.chain((channel_beginning,), (itertools.chain.from_iterable(ranges)))
                gaps = [(x, y) for x, y in zip(flat, flat) if x < y]
                for gap in gaps:
                    self.gaps[gap].append(channel_id)


    def json(self):
        return {
            'guilds': self.guilds,
            'num_runs': self.num_runs,
            'gaps': {f"{p[0]} - {p[1]}":v for p,v in self.gaps}
        }

def summary(path, as_json=False):
    path = Path(path)

    summarize = Summarize()
    summarize.parse_directory(path)
    
    if as_json:
        summary = summarize.json()
        print(json.dumps(summary))
    else:
        num_guilds = len(summarize.guilds)
        num_channels = sum([len(guild['channels']) for guild in summarize.guilds.values()])
        print(f"{summarize.num_runs} runs")
        print(f"{num_guilds} guilds")
        print(f"{num_channels} channels")
        print("Gaps:")
        for gap, channels in summarize.gaps.items():
            if len(channels) < 5:
                print(f"{gap}: {len(channels)} channels: {channels}")
            else:
                print(f"{gap}: {len(channels)} channels")
