import discord
import os
from redbot.core import commands, Config

class WormHole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="wormhole", force_registration=True)
        self.config.register_global(linked_channels_list=[], user_blacklist=[])  # Initialize the configuration

        self.bot.loop.create_task(self.setup_listeners())

    async def setup_listeners(self):
        await self.bot.wait_until_ready()
        self.bot.add_listener(self.on_source_message, "on_message")

    async def send_status_message(self, message, channel):
        linked_channels = await self.config.linked_channels_list()
        guild = channel.guild
        for channel_id in linked_channels:
            relay_channel = self.bot.get_channel(channel_id)
            if relay_channel and relay_channel != channel:
                await relay_channel.send(f"***The wormhole is shifting...** {guild.name}: {message}*")

    @commands.group()
    async def wormhole(self, ctx):
        """Manage wormhole connections."""
        pass

    @wormhole.command(name="open")
    async def wormhole_open(self, ctx):
        """Link the current channel to the network."""
        linked_channels = await self.config.linked_channels_list()
        if ctx.channel.id not in linked_channels:
            linked_channels.append(ctx.channel.id)
            await self.config.linked_channels_list.set(linked_channels)
            await ctx.send("This channel has joined the ever-changing maelstrom that is the wormhole.")
            await self.send_status_message(f"A faint signal was picked up from {ctx.channel.mention}, connection has been established.", ctx.channel)
        else:
            await ctx.send("This channel is already part of the wormhole.")

    @wormhole.command(name="close")
    async def wormhole_close(self, ctx):
        """Unlink the current channel from the network."""
        linked_channels = await self.config.linked_channels_list()
        if ctx.channel.id in linked_channels:
            linked_channels.remove(ctx.channel.id)
            await self.config.linked_channels_list.set(linked_channels)
            await ctx.send("This channel has been severed from the wormhole.")
            await self.send_status_message(f"The signal from {ctx.channel.mention} has become too faint to be picked up, the connection was lost.", ctx.channel)
        else:
            await ctx.send("This channel is not part of the wormhole.")

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not message.guild:  # Don't allow in DMs
            return
        if message.author.bot or not message.channel.permissions_for(message.guild.me).send_messages:
            return
        if isinstance(message.channel, discord.TextChannel) and message.content.startswith(commands.when_mentioned(self.bot, message)[0]):
            return  # Ignore bot commands

        linked_channels = await self.config.linked_channels_list()
        guild = message.guild
        author = message.author
        if message.channel.id in linked_channels and author.id not in await self.config.user_blacklist():
            for channel_id in linked_channels:
                if channel_id != message.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        display_name = author.display_name if author.display_name else author.name
                        if message.attachments:
                            for attachment in message.attachments:
                                await channel.send(f"**{guild.name} - {display_name}:** {message.content}")
                                await attachment.save(f"temp_{attachment.filename}")
                                with open(f"temp_{attachment.filename}", "rb") as file:
                                    await channel.send(file=discord.File(file))
                                os.remove(f"temp_{attachment.filename}")
                        else:
                            await channel.send(f"**{guild.name} - {display_name}:** {message.content}")

    @wormhole.command()
    async def blacklist(self, ctx, user: discord.User):
        """Command to prevent the wormhole from relaying messages sent by the targeted user."""
        user_blacklist = await self.config.user_blacklist()
        if user.id not in user_blacklist:
            user_blacklist.append(user.id)
            await self.config.user_blacklist.set(user_blacklist)
            await ctx.send(f"{user.display_name} has been added to the wormhole blacklist.")
        else:
            await ctx.send(f"{user.display_name} is already in the wormhole blacklist.")

def setup(bot):
    bot.add_cog(WormHole(bot))
