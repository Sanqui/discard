import json
import os
import gzip

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
    state.clear()

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
                message = discord.Message(state=state, channel=None, data=message_data)
                if message.type == discord.MessageType.default:
                    print(f"[{message.created_at}] <{message.author}> {message.content}")
                else:
                    print(f"[{message.created_at}] {message.system_content}")
