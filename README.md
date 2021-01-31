# Discard - Discord backups in archival quality.

Discard is a Python tool for medium-scale Discord server archival operations.

I don't know who needs to hear this, but I'll give a brief history lesson.  We used to own our data, now everything's in the cloud.  It used to be that chat clients had a valuable feature called *logging*.  Every message that you sent or received would be forever etched into a file on your disk, free to browse offline and search through in the future.  It's no longer like that.  We're supposed to appreciate the fulltext, fuzzy search we get from Discord, but something is lost.  The chat history is locked in this silo with no download option.  People can even delete their messages in front of your eyes—or while you're not looking!  This is not reasonable.  You deserve to trust your memory.

At [Archive Team](https://archiveteam.org/), we're working tirelessly to preserve websites at risk.  With this project I'm turning my attention to archiving Discord servers.  This is important because **our history matters**.  Closed services like Discord and Telegram have gone on to displace traditional services like message boards and even what used to be homepages.  Want to download my fan game?  Why don't you join my Discord?  The invite link is public, and once you join, all history is there for you to read.  Yet you can't **discover** content from the server by search.  Private, or public?  Discord's status is *deep web*, as chats are unable to be indexed by conventional search engines and archival tools, even if invites are posted publicly.

I'm taking a stance: if a Discord server has a public invite, you have the right to archive it.  Let's make that happen.

## Usage

The program needs a **Discord token** to operate.  It's compatible with both bot and user tokens.  Please check out [this guide](https://github.com/Tyrrrz/DiscordChatExporter/wiki/Obtaining-Token-and-Channel-IDs) on obtaining tokens.  The token can be provided on the command line with the `-t` parameter, or it can be read from a `DISCORD_TOKEN` enviromental variable (recommended if you want to avoid logging the token).

```
    $ python -m discard profile
```

Attempt to log in and display basic profile information.

```
    $ python -m discard run -g <guild1_id>,<guild2_id> --from <date> --to <date>
```

Perform an archival run for the given guilds in the given date range.

Discard is designed to run daily incremental backups.  The feasibility of a realtime archiver is due future study.

## Output
Discard outputs JSON files with the following directory structure:

```
    <run datetime>/
    |___run.meta.json
    |___run.json
    |___<guild_id>/
        |___guild.meta.json
        |___guild.json
        |___<channel_id>.meta.json
        |___<channel_id>.json
```

The `run.meta.json` file contains metadata about the run:

```json
{
    "client": {
        "name": "discard",
        "version": "0.0.0",
        "commit": "0123deadbeef"
    },
    "command": "python -m discard run --from 2020-12-14T00:00:00 --to 2020-12-15T00:00:00",
    "run_uuid": "7b6034d9-6290-47a5-9e3e-a6db23a2dd05",
    "datetime_start": "2020-12-15T13:00:19",
    "datetime_end": "2020-12-15T14:00:19",
    "completed": true,
    "errors": false,
    "exception": null,
    "requests": 125
}
```

It is written when the archival starts and again when it finishes correctly or when it terminates in case of an error.  In particular, note the exact version of the client as well as the command used for the backup run.

The "non-meta" files contain lists of HTTP requests and websocket exchanges as in the following example:
```json
[
    {
        "type": "http",
        "datetime": "2020-12-15T13:10:19",
        "request": {
            "method": "GET",
            "url": "/api/v8/channels/716047609776832626/messages"
        },
        "response": {
            "json": {...}
        }
    },
    {
        "type": "ws",
        "datetime": "2020-12-15T13:10:19",
        "response": {
            "json": {...}
        }
    ...
]
```

Typically the following requests are made:

* run.json
    * standard login requests with sensitive information stripped out
    * `GET /api/v8/users/@me`
    * guild discovery
* guild.json
    * ...
* <channel_id>.json
    * `GET api/v8/channels/<channel_id>/messages?limit=50` while in the desired range
    * when encountering an invite: `GET /api/v8/invites/<invite_id>`

## Why not use [DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter)?

[DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) is an excellent tool for end users.  If you're a single person who wants to make a few backups, please, **go ahead and use it**.  It has a straightforward GUI and multiple formatting options, particularly HTML, which allows for exporting chat logs that are easy to browse.  I've even made a brief contribution myself.

What does Discard do differently?  Discard is a more advanced archival tool.  Its goal is to **record Discord API responses** with minimal data processing.  This allows for certainty that no data is missed, even for exotic types of content, or in case Discord changes its API.  The data can then further be derived by other tools.

In particular, I hope to address these issues with DiscordChatExporter which have been marked as out of scope:

* While Discord's API is JSON, the JSON files exported by DiscordChatExporter are processed and differ in field names ([#454](https://github.com/Tyrrrz/DiscordChatExporter/issues/454))
* DiscordChatExporter doesn't download full resolution images, even when they are available ([#346](https://github.com/Tyrrrz/DiscordChatExporter/issues/346))
* Users in a Discord server are not downloaded ([#104](https://github.com/Tyrrrz/DiscordChatExporter/issues/104))
* Authors of reactions are not fetched ([#133](https://github.com/Tyrrrz/DiscordChatExporter/issues/133))

Again, none of this is to flak DiscordChatExporter, the two projects simply have different goals.

## Disclaimer

The use of *data mining, robots, spiders, or similar data gathering and extraction tools* is against Discord's [Terms of Service](https://discord.com/terms).  Use at your own risk.
