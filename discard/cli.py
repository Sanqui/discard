import sys
import datetime
from pathlib import Path

import click

from discard import Discard
from discard import reader

@click.group()
@click.option('-t', '--token', required=True, help='Bot or user token.',
            envvar='DISCORD_TOKEN')
@click.option('-U', '--is-user-account', default=False, is_flag=True, help='Log in as a user account.')
@click.option('-o', '--output-dir', default=Path('out/'), help='Output directory, out/ by default.',
                type=click.Path(file_okay=False, writable=True))
@click.option('--after', help="Datetime after which to retrieve history (UTC)", type=click.DateTime())
@click.option('--before', help="Datetime before which to retrieve history (UTC)", type=click.DateTime())
@click.option('--no-scrub', default=False, is_flag=True, help='Do not scrub token from logged data.')
@click.option('--gzip', default=False, is_flag=True, help='Save logs compressed with gzip.')
@click.pass_context
def cli(ctx, **kwargs):
    ctx.ensure_object(dict)

    ctx.obj.update(kwargs)
    ctx.obj['output_dir'] = Path(ctx.obj['output_dir'])
    ctx.obj['command'] = sys.argv

@cli.command(help="Only log in and fetch profile information.")
@click.pass_context
def profile(ctx):
    discard = Discard(mode="profile", **ctx.obj)
    discard.run()

@cli.command(help="Archive one or multiple channels.")
@click.argument('channel_id', required=True, nargs=-1, type=int)
@click.pass_context
def channel(ctx, channel_id):
    discard = Discard(mode="channel", channel_id=channel_id, **ctx.obj)
    discard.run()

@cli.command(help="Archive one or multiple guilds.")
@click.argument('guild_id', required=True, nargs=-1, type=int)
@click.pass_context
def guild(ctx, guild_id):
    discard = Discard(mode="guild", guild_id=guild_id, **ctx.obj)
    discard.run()

@cli.command(help="Read a channel log.")
@click.argument('path', required=True, type=click.Path(file_okay=False))
@click.pass_context
def read(ctx, path):
    reader.read_chat(path)

if __name__ == '__main__':
    cli()