import sys
import datetime

import click

from discard import Discard

@click.group()
@click.option('-t', '--token', required=True, help='Bot or user token.',
            envvar='DISCORD_TOKEN')
@click.option('-U', '--is-user-account', default=False, is_flag=True, help='Log in as a user account.')
@click.option('-o', '--output-dir', default='out/', help='Output directory, out/ by default.',
                type=click.Path(file_okay=False, writable=True))
@click.option('--after', help="Datetime after which to retrieve history (UTC)", type=click.DateTime())
@click.option('--before', help="Datetime before which to retrieve history (UTC)", type=click.DateTime())
@click.option('--no-scrub', default=False, is_flag=True, help='Do not scrub token from logged data.')
@click.pass_context
def cli(ctx, **kwargs):
    ctx.ensure_object(dict)

    ctx.obj.update(kwargs)
    ctx.obj['command'] = sys.argv

@cli.command(help="Only log in and fetch profile information.")
@click.pass_context
def profile(ctx):
    discard = Discard(mode="profile", **ctx.obj)
    discard.run()

@cli.command(help="Archive a single channel.")
@click.argument('channel_id', required=True, type=int)
@click.pass_context
def channel(ctx, channel_id):
    discard = Discard(mode="channel", channel_id=channel_id, **ctx.obj)
    discard.run()

@cli.command(help="Archive a single guild.")
@click.argument('guild_id', required=True, type=int)
@click.pass_context
def guild(ctx, guild_id):
    discard = Discard(mode="guild", guild_id=guild_id, **ctx.obj)
    discard.run()

if __name__ == '__main__':
    cli()