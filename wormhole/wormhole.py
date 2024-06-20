import discord
import os
from redbot.core import commands, Config

class WormHole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="wormhole", force_registration=True)
        self.config.register_global(linked_channels_list_1=[], linked_channels_list_2=[], linked_channels_list_3=[], user_blacklist=[], word_filters=[], global_blacklist=[])  # Initialize the configuration

        self.bot.loop.create_task(self.setup_listeners())

    async def setup_listeners(self):
        await self.bot.wait_until_ready()
        self.bot.add_listener(self.on_source_message, "on_message")

    async def send_status_message(self, message, channel, wormhole_number):
        linked_channels = await self.config.get_raw(f'linked_channels_list_{wormhole_number}')
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
    async def wormhole_open(self, ctx, wormhole_number: int):
        """Link the current channel to the specified wormhole network."""
        if wormhole_number not in [1, 2, 3]:
            await ctx.send("Invalid wormhole number. Please choose 1, 2, or 3.")
            return

        linked_channels = await self.config.get_raw(f'linked_channels_list_{wormhole_number}')
        if ctx.channel.id not in linked_channels:
            linked_channels.append(ctx.channel.id)
            await self.config.set_raw(f'linked_channels_list_{wormhole_number}', value=linked_channels)
            await ctx.send(f"This channel has joined wormhole {wormhole_number}.")
            await self.send_status_message(f"A faint signal was picked up from {ctx.channel.mention}, connection has been established.", ctx.channel, wormhole_number)
        else:
            await ctx.send("This channel is already part of the wormhole.")

    @wormhole.command(name="close")
    async def wormhole_close(self, ctx, wormhole_number: int):
        """Unlink the current channel from the specified wormhole network."""
        if wormhole_number not in [1, 2, 3]:
            await ctx.send("Invalid wormhole number. Please choose 1, 2, or 3.")
            return

        linked_channels = await self.config.get_raw(f'linked_channels_list_{wormhole_number}')
        if ctx.channel.id in linked_channels:
            linked_channels.remove(ctx.channel.id)
            await self.config.set_raw(f'linked_channels_list_{wormhole_number}', value=linked_channels)
            await ctx.send(f"This channel has been severed from wormhole {wormhole_number}.")
            await self.send_status_message(f"The signal from {ctx.channel.mention} has become too faint to be picked up, the connection was lost.", ctx.channel, wormhole_number)
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

        global_blacklist = await self.config.global_blacklist()
        word_filters = await self.config.word_filters()

        if message.author.id in await self.config.user_blacklist() or message.author.id in global_blacklist:
            return  # Author is blacklisted

        if any(word in message.content for word in word_filters):
            return  # Message contains a filtered word, ignore it

        for wormhole_number in [1, 2, 3]:
            linked_channels = await self.config.get_raw(f'linked_channels_list_{wormhole_number}')
            if message.channel.id in linked_channels:
                for channel_id in linked_channels:
                    if channel_id != message.channel.id:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            display_name = message.author.display_name if message.author.display_name else message.author.name
                            content = message.content
                            for emoji in message.emojis:
                                if not self.bot.get_emoji(emoji.id):
                                    content = content.replace(str(emoji), f"https://cdn.discordapp.com/emojis/{emoji.id}.png")

                            if message.attachments:
                                for attachment in message.attachments:
                                    await channel.send(f"**{message.guild.name} - {display_name}:** {content}")
                                    await attachment.save(f"temp_{attachment.filename}")
                                    with open(f"temp_{attachment.filename}", "rb") as file:
                                        await channel.send(file=discord.File(file))
                                    os.remove(f"temp_{attachment.filename}")
                            else:
                                await channel.send(f"**{message.guild.name} - {display_name}:** {content}")

    @wormhole.command()
    async def blacklist(self, ctx, user: discord.User):
        """Prevent specific members from sending messages through the wormhole."""
        if await self.bot.is_owner(ctx.author):
            user_blacklist = await self.config.user_blacklist()
            if user.id not in user_blacklist:
                user_blacklist.append(user.id)
                await self.config.user_blacklist.set(user_blacklist)
                await ctx.send(f"{user.display_name} has been added to the wormhole blacklist.")
            else:
                await ctx.send(f"{user.display_name} is already in the wormhole blacklist.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="unblacklist")
    async def wormhole_unblacklist(self, ctx, user: discord.User):
        """Command to remove a user from the wormhole blacklist (Bot Owner Only)."""
        if await self.bot.is_owner(ctx.author):
            user_blacklist = await self.config.user_blacklist()
            if user.id in user_blacklist:
                user_blacklist.remove(user.id)
                await self.config.user_blacklist.set(user_blacklist)
                await ctx.send(f"{user.display_name} has been removed from the wormhole blacklist.")
            else:
                await ctx.send(f"{user.display_name} is not in the wormhole blacklist.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="globalblacklist")
    async def wormhole_globalblacklist(self, ctx, user: discord.User):
        """Prevent specific members from sending messages through the wormhole globally."""
        if await self.bot.is_owner(ctx.author):
            global_blacklist = await self.config.global_blacklist()
            if user.id not in global_blacklist:
                global_blacklist.append(user.id)
                await self.config.global_blacklist.set(global_blacklist)
                await ctx.send(f"{user.display_name} has been added to the global wormhole blacklist.")
            else:
                await ctx.send(f"{user.display_name} is already in the global wormhole blacklist.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="unglobalblacklist")
    async def wormhole_unglobalblacklist(self, ctx, user: discord.User):
        """Command to remove a user from the global wormhole blacklist (Bot Owner Only)."""
        if await self.bot.is_owner(ctx.author):
            global_blacklist = await self.config.global_blacklist()
            if user.id in global_blacklist:
                global_blacklist.remove(user.id)
                await self.config.global_blacklist.set(global_blacklist)
                await ctx.send(f"{user.display_name} has been removed from the global wormhole blacklist.")
            else:
                await ctx.send(f"{user.display_name} is not in the global wormhole blacklist.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="addwordfilter")
    async def wormhole_addwordfilter(self, ctx, *, word: str):
        """Add a word to the wormhole word filter."""
        if await self.bot.is_owner(ctx.author):
            word_filters = await self.config.word_filters()
            if word not in word_filters:
                word_filters.append(word)
                await self.config.word_filters.set(word_filters)
                await ctx.send(f"`{word}` has been added to the wormhole word filter.")
            else:
                await ctx.send(f"`{word}` is already in the wormhole word filter.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

    @wormhole.command(name="removewordfilter")
    async def wormhole_removewordfilter(self, ctx, *, word: str):
        """Remove a word from the wormhole word filter."""
        if await self.bot.is_owner(ctx.author):
            word_filters = await self.config.word_filters()
            if word in word_filters:
                word_filters.remove(word)
                await self.config.word_filters.set(word_filters)
                await ctx.send(f"`{word}` has been removed from the wormhole word filter.")
            else:
                await ctx.send(f"`{word}` is not in the wormhole word filter.")
        else:
            await ctx.send("You must be the bot owner to use this command.")

def setup(bot):
    bot.add_cog(WormHole(bot))
