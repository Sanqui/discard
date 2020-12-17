import vcr
import discord
import logging

#logging.basicConfig(level=logging.DEBUG)

TOKEN = ''

client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    channel = client.get_channel(776428229270437908)
    print(channel.name)
    await channel.send('hello')

@client.event
async def on_socket_raw_send(payload):
    print(">>>", payload)

@client.event
async def on_socket_response(msg):
    print("<<<", msg)

#with vcr.use_cassette('fixtures/vcr_cassettes/test4.yaml'):
client.run(TOKEN)
