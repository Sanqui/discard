# Discard - Discord backups in archival quality.

Discard is a Python tool for medium-scale Discord server archival operations.

I don't know who needs to hear this, but I'll give a brief history lesson.  We used to own our data, now everything's in the cloud.  It used to be that chat clients had a valuable feature called *logging*.  Every message that you sent or received would be forever etched into a file on your disk, free to browse offline and search through in the future.  It's no longer like that.  We're supposed to appreciate the fulltext, fuzzy search we get from Discord, but something is lost.  The chat history is locked in this silo with no download option.  People can even delete their messages in front of your eyes—or while you're not looking!  This is not reasonable.  You deserve to trust your memory.

At [Archive Team](https://archiveteam.org/), we're working tirelessly to preserve websites at risk.  With this project I'm turning my attention to archiving Discord servers.  This is important because **our history matters**.  Closed services like Discord and Telegram have gone on to displace traditional services like message boards and even what used to be homepages.  Want to download my fan game?  Why don't you join my Discord?  The invite link is public, and once you join, all history is there for you to read.  Yet you can't **discover** content from the server by search.  Private, or public?  Discord's status is *deep web*, as chats are unable to be indexed by conventional search engines and archival tools, even if invites are posted publicly.

I'm taking a stance: if a Discord server has a public invite, you have the right to archive it.  Let's make that happen.

## Usage
Discard is a Python command-line utility as well as a library.

Discard needs a **Discord token** to operate.  It's compatible with both bot and user tokens.  Please check out [this guide](https://github.com/Tyrrrz/DiscordChatExporter/wiki/Obtaining-Token-and-Channel-IDs) on obtaining tokens.  The token can be provided on the command line with the `-t` parameter, or it can be read from a `DISCORD_TOKEN` enviromental variable (recommended if you want to avoid logging the token).


```
    $ python -m discard profile
```

Attempt to log in and display basic profile information.

```
    $ python -m discard channel <channel_id>
```

Perform an archival run for the given channel in its entirety.  Multiple IDs may be provided.

```
    $ python -m discard --after <datetime> --before <datetime> guild <guild_id>
```

Archive all messages accessible in a given Discord guild within the given time range.  Multiple IDs may be provided.

The following command-line options are available:

```
  -t, --token TEXT                Bot or user token.  [required]
  -U, --is-user-account           Log in as a user account.
  -o, --output-dir DIRECTORY      Output directory, out/ by default.
  --after [%Y-%m-%d|%Y-%m-%dT%H:%M:%S]
                                  Datetime after which to retrieve history (UTC)
  --before [%Y-%m-%d|%Y-%m-%dT%H:%M:%S]
                                  Datetime before which to retrieve history (UTC)
  --no-scrub                      Do not scrub token from logged data.
  --gzip                          Save logs compressed with gzip.
```

Discard is designed to create one-shot archives of the entire chatlog as well as for daily incremental backups.  The feasibility of a realtime archiver is due future study.

## Output
You can find example output from a single guild run in the example/ directory of this repository.

In the specified output directory, Discord creates a new directory for the current run and saves JSON files with the following structure:

```
    <run_datetime>_<mode>/
    |___run.meta.json
    |___run.jsonl
    |___<guild_id>/
        |___guild.meta.json
        |___guild.jsonl
        |___<channel_id>.meta.json
        |___<channel_id>.jsonl
        ...
    ...
```

The `run.meta.json` file contains metadata about the run.  It saves the current client version, the exact command used to launch the run, settings, details about the run progress, and a summary of the gathered data.  It is written when the run is started and again when it finishes correctly or when it terminates in case of an error.

The JSONL files contain newline separated objects describing HTTP requests and websocket exchanges pertaining to the given run, guild, or channel.  These files are an exact log of the interactions made with the Discord API in order to gather all relevant information.  They are streamed and can optionally be compressed in the GZIP format.

Typically the following requests are made:

* run.jsonl
    * `GET /api/v7/users/@me`
    * `GET /api/v7/gateway`
    * Standard websocket interactions
* `<guild_id>`/guild.jsonl
    * `GET /api/v7/guilds/<guild_id>`
    * `GET /api/v7/guilds/<guild_id>/channels`
    * TODO: fetch webhooks if there is permission
* `<guild_id>`/`<channel_id>`.jsonl
    * `GET api/v8/channels/<channel_id>/messages?limit=100` while in the desired range
    * TODO: when encountering an invite: `GET /api/v8/invites/<invite_id>`
    * TODO: when encountering a reaction

## Why not use [DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter)?

[DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) is an excellent tool for end users.  If you're somebody who just wants to make a few backups, please, **go ahead and use it**.  It has a straightforward GUI and multiple formatting options, particularly HTML, which allows for exporting chat logs that are easy to browse.  I've even made a brief contribution myself.

What does Discard do differently?  Discard is a more advanced archival tool.  Its goal is to **record Discord API responses** with minimal data processing.  This allows for certainty that no data is missed, even for exotic types of content, or in case Discord changes its API (such as when replies were introduced!).  The idea is that as long as the data is complete, it can always be further derived by other tools.

In particular, I hope to address these issues with DiscordChatExporter which have been marked as out of scope:

* While Discord's API is JSON, the JSON files exported by DiscordChatExporter are processed and differ in field names ([#454](https://github.com/Tyrrrz/DiscordChatExporter/issues/454))
* DiscordChatExporter doesn't download full resolution images, even when they are available ([#346](https://github.com/Tyrrrz/DiscordChatExporter/issues/346))
* Users in a Discord server are not downloaded ([#104](https://github.com/Tyrrrz/DiscordChatExporter/issues/104))
* Authors of reactions are not fetched ([#133](https://github.com/Tyrrrz/DiscordChatExporter/issues/133))

There is no intention to diss DiscordChatExporter, the two projects simply have different goals.

## Disclaimer

The use of *data mining, robots, spiders, or similar data gathering and extraction tools* is against Discord's [Terms of Service](https://discord.com/terms).  Use at your own risk.
