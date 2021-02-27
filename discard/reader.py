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
