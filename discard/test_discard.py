import json
import gzip
from pathlib import Path

import discord
import pytest

from discard import Discard

# This is set to a valid token for recording cassettes but scrubbed in the repo.
TEST_TOKEN = 'aa.bb.cc'

# This is the test user that was used for generating fixtures.
# This information is typically retrieved over Websocket, but we can't
# currently mock that, so we're mocking the user directly.
TEST_USER = discord.User(state=None, data={
    'id': 788430627179462657,
    'username': 'DiscardTest',
    'discriminator': '9433',
    'bot': True,
    'avatar': None
})

# We cannot instantiate the Guild class directly because we have no state object,
# but we barely need it for anything so let's get around that
TEST_GUILD = discord.Guild.__new__(discord.Guild)
TEST_GUILD.id = 716047609776832623
TEST_GUILD.name = "Discard Test Server"
TEST_GUILD._members = {}

TEST_CHANNEL = discord.TextChannel(state=None, guild=TEST_GUILD, data={
    'id': 805808489695150183,
    'type': 0,
    'name': 'general',
    'parent_id': 0, 'position': 0
})

@pytest.fixture(scope="module")
def vcr_config():
    return {"filter_headers": ["authorization", "Sec-WebSocket-Key"]}


def monkeypatch_discard(monkeypatch, discard):
    # We don't get networking and VCR doesn't capture websocket, so dummy it out
    async def connect(reconnect=True):
        # We would have received user information over WS
        discard.client._connection.user = TEST_USER
        # After that on_ready would be called
        await discard.client.on_ready()
    
    def get_channel(channel_id):
        if channel_id == TEST_CHANNEL.id:
            TEST_CHANNEL._state = discard.client._connection
            return TEST_CHANNEL
        else:
            raise discord.discord.NotFoundError()
        
    monkeypatch.setattr(discard.client, 'connect', connect)
    monkeypatch.setattr(discard.client, 'get_channel', get_channel)

    return discard


@pytest.mark.asyncio
@pytest.mark.vcr
@pytest.mark.block_network
def test_profile(tmp_path, monkeypatch):
    discard = Discard(mode="profile", token=TEST_TOKEN, output_dir=tmp_path)
    monkeypatch_discard(monkeypatch, discard)

    discard.run()

    directories = list(tmp_path.iterdir())
    
    assert len(directories) == 1
    
    run_directory = directories[0]
    
    with open(run_directory / 'run.meta.json') as f:
        obj = json.load(f)
        assert obj['client']['name'] == 'discard'
        assert obj['settings']['mode'] == 'profile'
        assert obj['settings']['token'] == None
        assert obj['run']['completed'] == True
        assert obj['run']['finished'] == True
        assert obj['run']['errors'] == False
        assert obj['run']['exception'] == None
        assert obj['user']['name'] == 'DiscardTest'

    with open(run_directory / 'run.jsonl') as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                assert obj['type'] in ['http', 'ws']


@pytest.mark.asyncio
@pytest.mark.vcr
@pytest.mark.block_network
def test_wrong_token(tmp_path, monkeypatch):
    discard = Discard(mode="profile", token="incorrect", output_dir=tmp_path)
    monkeypatch_discard(monkeypatch, discard)

    with pytest.raises(discord.errors.LoginFailure):
        discard.run()
    
    run_directory = list(tmp_path.iterdir())[0]
    
    with open(run_directory / 'run.meta.json') as f:
        obj = json.load(f)
        assert obj['run']['completed'] == False
        assert obj['run']['finished'] == True
        assert obj['run']['errors'] == True
        assert obj['run']['exception'].startswith('LoginFailure')


@pytest.mark.asyncio
@pytest.mark.vcr
@pytest.mark.block_network
def test_channel(tmp_path, monkeypatch):
    discard = Discard(mode="channel", channel_id=TEST_CHANNEL.id, token=TEST_TOKEN, output_dir=tmp_path)
    monkeypatch_discard(monkeypatch, discard)

    discard.run()

    run_directory = list(tmp_path.iterdir())[0]
    
    with open(run_directory / 'run.meta.json') as f:
        obj = json.load(f)
        assert obj['client']['name'] == 'discard'
        assert obj['settings']['mode'] == 'channel'
        assert obj['run']['completed'] == True
        assert obj['run']['finished'] == True
        assert obj['run']['errors'] == False
        assert obj['run']['exception'] == None

    with open(run_directory / 'run.jsonl') as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                assert obj['type'] in ['http', 'ws']

    with open(run_directory / Path(str(TEST_GUILD.id)) / Path(f"{TEST_CHANNEL.id}.meta.json")) as f:
        obj = json.load(f)
        assert obj['channel']['id'] == TEST_CHANNEL.id
        assert obj['channel']['name'] == TEST_CHANNEL.name
        assert obj['summary']['num_messages'] > 0
    
    with open(run_directory / Path(str(TEST_GUILD.id)) / Path(f"{TEST_CHANNEL.id}.jsonl")) as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                assert obj['type'] in ['http', 'ws']


@pytest.mark.asyncio
@pytest.mark.vcr
@pytest.mark.block_network
def test_gzip(tmp_path, monkeypatch):
    discard = Discard(mode="profile", token=TEST_TOKEN, output_dir=tmp_path, gzip=True)
    monkeypatch_discard(monkeypatch, discard)

    discard.run()

    run_directory = list(tmp_path.iterdir())[0]
    
    with open(run_directory / 'run.meta.json') as f:
        obj = json.load(f)
        assert obj['settings']['gzip'] == True
    
    with gzip.open(str(run_directory / 'run.jsonl.gz')) as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                assert obj['type'] in ['http', 'ws']

