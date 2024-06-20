import discord
import os
from redbot.core import commands, Config

class WormHole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="wormhole", force_registration=True)
        self.config.register_global(
            linked_channels_list=[],
            global_blacklist=[],
            word_filters=[]
        )  # Initialize the configuration

    async def send_status_message(self, message, channel):
        linked_channels = await self.config.linked_channels_list()
        guild = channel.guild
        for channel_id in linked_channels:
            relay_channel = self.bot.get_channel(channel_id)
            if relay_channel and relay_channel != channel:
                await relay_channel.send(f"***The wormhole is shifting...** {guild.name}: {message}*")

    @commands.group()
    async def wormhole(self, ctx):
        """Manage public wormhole connections."""
        pass

    @wormhole.command(name="open")
    async def wormhole_open(self, ctx):
        """Link the current channel to the public wormhole network."""
        linked_channels = await self.config.linked_channels_list()
        if ctx.channel.id not in linked_channels:
            linked_channels.append(ctx.channel.id)
            await self.config.linked_channels_list.set(linked_channels)
            await ctx.send("This channel has joined the ever-changing maelstrom that is the public wormhole.")
            await self.send_status_message(f"A faint signal was picked up from {ctx.channel.mention}, connection has been established.", ctx.channel)
        else:
            await ctx.send("This channel is already part of the public wormhole.")

    @wormhole.command(name="close")
    async def wormhole_close(self, ctx):
        """Unlink the current channel from the public wormhole network."""
        linked_channels = await self.config.linked_channels_list()
        if ctx.channel.id in linked_channels:
            linked_channels.remove(ctx.channel.id)
            await self.config.linked_channels_list.set(linked_channels)
            await ctx.send("This channel has been severed from the public wormhole.")
            await self.send_status_message(f"The signal from {ctx.channel.mention} has become too faint to be picked up, the connection was lost.", ctx.channel)
        else:
            await ctx.send("This channel is not part of the public wormhole.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:  # Don't allow in DMs
            return
        if message.author.bot or not message.channel.permissions_for(message.guild.me).send_messages:
            return
        if isinstance(message.channel, discord.TextChannel) and message.content.startswith(commands.when_mentioned(self.bot, message)[0]):
            return  # Ignore bot commands

        # Check if the message is a bot command
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return  # Ignore bot commands

        linked_channels = await self.config.linked_channels_list()
        global_blacklist = await self.config.global_blacklist()
        word_filters = await self.config.word_filters()

        if message.author.id in global_blacklist:
            return  # Author is globally blacklisted

        if any(word in message.content for word in word_filters):
            await message.channel.send("That word is not allowed.")
            await message.delete()
            return  # Message contains a filtered word, notify user and delete it

        if message.channel.is_nsfw():
            await message.channel.send("NSFW content is not allowed in the wormhole.")
            await message.delete()
            return  # Delete NSFW messages

        if "@everyone" in message.content or "@here" in message.content:
            await message.channel.send("`@everyone` and `@here` pings are not allowed.")
            await message.delete()
            return  # Message contains prohibited pings, notify user and delete it

        display_name = message.author.display_name if message.author.display_name else message.author.name

        # Check if the message is in a public wormhole channel
        if message.channel.id in linked_channels:
            for channel_id in linked_channels:
                if channel_id != message.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        if message.attachments:
                            for attachment in message.attachments:
                                await channel.send(f"**{message.guild.name} - {display_name}:** {message.content}")
                                await attachment.save(f"temp_{attachment.filename}")
                                with open(f"temp_{attachment.filename}", "rb") as file:
                                    await channel.send(file=discord.File(file))
                                os.remove(f"temp_{attachment.filename}")
                        else:
                            await channel.send(f"**{message.guild.name} - {display_name}:** {message.content}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild:
            return

        linked_channels = await self.config.linked_channels_list()

        # Check if the message is in a public wormhole channel
        if message.channel.id in linked_channels:
            for channel_id in linked_channels:
                if channel_id != message.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        async for msg in channel.history(limit=100):
                            if msg.content == f"**{message.guild.name} - {message.author.display_name}:** {message.content}":
                                await msg.delete()
                                break

    @wormhole.command(name="globalblacklist")
    async def wormhole_globalblacklist(self, ctx, user: discord.User):
        """Prevent specific members from sending messages through the public wormhole globally."""
        if await self.bot.is_owner(ctx.author):
            global_blacklist = await self.config.global_blacklist()
            if user.id not in global_blacklist:
                global_blacklist.append(user.id)
                await self.config.global_blacklist.set(global_blacklist)
                await ctx.send(f"{user.display_name} has been added to the global public wormhole blacklist.")
            else:
                await ctx.send(f"{user.display_name} is already in the global public wormhole blacklist.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="unglobalblacklist")
    async def wormhole_unglobalblacklist(self, ctx, user: discord.User):
        """Command to remove a user from the global public wormhole blacklist (Bot Owner Only)."""
        if await self.bot.is_owner(ctx.author):
            global_blacklist = await self.config.global_blacklist()
            if user.id in global_blacklist:
                global_blacklist.remove(user.id)
                await self.config.global_blacklist.set(global_blacklist)
                await ctx.send(f"{user.display_name} has been removed from the global public wormhole blacklist.")
            else:
                await ctx.send(f"{user.display_name} is not in the global public wormhole blacklist.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="addwordfilter")
    async def wormhole_addwordfilter(self, ctx, *, word: str):
        """Add a word to the public wormhole word filter."""
        if await self.bot.is_owner(ctx.author):
            word_filters = await self.config.word_filters()
            if word not in word_filters:
                word_filters.append(word)
                await self.config.word_filters.set(word_filters)
                await ctx.send(f"`{word}` has been added to the public wormhole word filter.")
            else:
                await ctx.send(f"`{word}` is already in the public wormhole word filter.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="removewordfilter")
    async def wormhole_removewordfilter(self, ctx, *, word: str):
        """Remove a word from the public wormhole word filter."""
        if await self.bot.is_owner(ctx.author):
            word_filters = await self.config.word_filters()
            if word in word_filters:
                word_filters.remove(word)
                await self.config.word_filters.set(word_filters)
                await ctx.send(f"`{word}` has been removed from the public wormhole word filter.")
            else:
                await ctx.send(f"`{word}` is not in the public wormhole word filter.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

def setup(bot):
    bot.add_cog(WormHole(bot))
