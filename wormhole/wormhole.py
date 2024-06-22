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
        self.message_references = {}  # Store message references
        self.relayed_messages = {}  # Store relayed messages

    async def send_status_message(self, message, channel, title):
        linked_channels = await self.config.linked_channels_list()
        guild = channel.guild
        embed = discord.Embed(title=title, description=f"{guild.name}: {message}")
        for channel_id in linked_channels:
            relay_channel = self.bot.get_channel(channel_id)
            if relay_channel and relay_channel != channel:
                await relay_channel.send(embed=embed)

    @commands.group(aliases=['wm'])
    async def wormhole(self, ctx):
        """Manage wormhole connections."""
        pass

    @wormhole.command(name="open")
    async def wormhole_open(self, ctx):
        """Link the current channel to the wormhole network."""
        linked_channels = await self.config.linked_channels_list()
        if ctx.channel.id not in linked_channels:
            linked_channels.append(ctx.channel.id)
            await self.config.linked_channels_list.set(linked_channels)
            embed = discord.Embed(title="Success!", description="This channel has joined the ever-changing maelstrom that is the wormhole.")
            await ctx.send(embed=embed)
            await self.send_status_message(f"A faint signal was picked up from {ctx.channel.mention}, connection has been established.", ctx.channel, "Success!")
        else:
            embed = discord.Embed(title="ErRoR 404", description="This channel is already part of the wormhole.")
            await ctx.send(embed=embed)

    @wormhole.command(name="close")
    async def wormhole_close(self, ctx):
        """Unlink the current channel from the wormhole network."""
        linked_channels = await self.config.linked_channels_list()
        if ctx.channel.id in linked_channels:
            linked_channels.remove(ctx.channel.id)
            await self.config.linked_channels_list.set(linked_channels)
            embed = discord.Embed(title="Success!", description="This channel has been severed from the wormhole.")
            await ctx.send(embed=embed)
            await self.send_status_message(f"The signal from {ctx.channel.mention} has become too faint to be picked up, the connection was lost.", ctx.channel, "Success!")
        else:
            embed = discord.Embed(title="ErRoR 404", description="This channel is not part of the wormhole.")
            await ctx.send(embed=embed)

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

        if message.channel.id in linked_channels:
            if any(word in message.content for word in word_filters):
                embed = discord.Embed(title="ErRoR 404", description="That word is not allowed.")
                await message.channel.send(embed=embed)
                await message.delete()
                return  # Message contains a filtered word, notify user and delete it

            if message.channel.is_nsfw():
                embed = discord.Embed(title="ErRoR 404", description="NSFW content is not allowed in the wormhole.")
                await message.channel.send(embed=embed)
                await message.delete()
                return  # Delete NSFW messages

            if "@everyone" in message.content or "@here" in message.content:
                embed = discord.Embed(title="ErRoR 404", description="`@everyone` and `@here` pings are not allowed.")
                await message.channel.send(embed=embed)
                await message.delete()
                return  # Message contains prohibited pings, notify user and delete it

            display_name = message.author.display_name if message.author.display_name else message.author.name

            # Store the message reference
            self.message_references[message.id] = (message.author.id, message.guild.id)

            # Relay the message to other linked channels, removing mentions
            content = message.content

            # Handle mentions
            mentioned_users = message.mentions
            if mentioned_users:
                for user in mentioned_users:
                    content = content.replace(f"<@{user.id}>", '')  # Remove the mention
                    embed = discord.Embed(title="You were mentioned!")
                    embed.add_field(name="Who", value=message.author.mention, inline=False)
                    embed.add_field(name="Where", value=f"{message.channel.mention} in {message.guild.name}", inline=False)
                    embed.add_field(name="When", value=message.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
                    await user.send(embed=embed)

            # If there's no content left after removing mentions
            if not content.strip():
                content = "User Mentioned Blocked"

            # Handle emojis
            for emoji in message.guild.emojis:
                if str(emoji) in message.content and not emoji.is_usable():
                    content = content.replace(str(emoji), emoji.url)

            for channel_id in linked_channels:
                if channel_id != message.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        if message.attachments:
                            for attachment in message.attachments:
                                relay_message = await channel.send(f"**{message.guild.name} - {display_name}:** {content}")
                                await attachment.save(f"temp_{attachment.filename}")
                                with open(f"temp_{attachment.filename}", "rb") as file:
                                    await channel.send(file=discord.File(file))
                                os.remove(f"temp_{attachment.filename}")
                        else:
                            relay_message = await channel.send(f"**{message.guild.name} - {display_name}:** {content}")
                        self.relayed_messages[(message.id, channel_id)] = relay_message.id

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not after.guild:
            return

        linked_channels = await self.config.linked_channels_list()

        if after.channel.id in linked_channels:
            display_name = after.author.display_name if after.author.display_name else after.author.name
            content = after.content

            # Handle mentions
            mentioned_users = after.mentions
            if mentioned_users:
                for user in mentioned_users:
                    content = content.replace(f"<@{user.id}>", '')  # Remove the mention
                    embed = discord.Embed(title="You were mentioned!")
                    embed.add_field(name="Who", value=after.author.mention, inline=False)
                    embed.add_field(name="Where", value=f"{after.channel.mention} in {after.guild.name}", inline=False)
                    embed.add_field(name="When", value=after.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
                    await user.send(embed=embed)

            # If there's no content left after removing mentions
            if not content.strip():
                content = "User Mentioned Blocked"

            # Handle emojis
            for emoji in after.guild.emojis:
                if str(emoji) in after.content and not emoji.is_usable():
                    content = content.replace(str(emoji), emoji.url)

            for channel_id in linked_channels:
                if channel_id != after.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        if (before.id, channel_id) in self.relayed_messages:
                            relay_message_id = self.relayed_messages[(before.id, channel_id)]
                            relay_message = await channel.fetch_message(relay_message_id)
                            await relay_message.delete()
                            new_relay_message = await channel.send(f"**{after.guild.name} - {display_name} (edited):** {content}")
                            self.relayed_messages[(after.id, channel_id)] = new_relay_message.id

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild:
            return

        linked_channels = await self.config.linked_channels_list()

        # Check if the message is in a wormhole channel
        if message.channel.id in linked_channels:
            for channel_id in linked_channels:
                if channel_id != message.channel.id:
                    channel = self.bot.get_channel(channel_id)
                    if channel and (message.id, channel_id) in self.relayed_messages:
                        relay_message_id = self.relayed_messages[(message.id, channel_id)]
                        relay_message = await channel.fetch_message(relay_message_id)
                        await relay_message.delete()

    @wormhole.command(name="globalblacklist")
    async def wormhole_globalblacklist(self, ctx, user: discord.User):
        """Prevent specific members from sending messages through the wormhole globally."""
        if await self.bot.is_owner(ctx.author):
            global_blacklist = await self.config.global_blacklist()
            if user.id not in global_blacklist:
                global_blacklist.append(user.id)
                await self.config.global_blacklist.set(global_blacklist)
                embed = discord.Embed(title="Success!", description=f"{user.display_name} has been added to the global wormhole blacklist.")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="ErRoR 404", description=f"{user.display_name} is already in the global wormhole blacklist.")
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description="You must be the bot owner to use this command.")
            await ctx.send(embed=embed)

    @wormhole.command(name="unglobalblacklist")
    async def wormhole_unglobalblacklist(self, ctx, user: discord.User):
        """Command to remove a user from the global wormhole blacklist (Bot Owner Only)."""
        if await self.bot.is_owner(ctx.author):
            global_blacklist = await self.config.global_blacklist()
            if user.id in global_blacklist:
                global_blacklist.remove(user.id)
                await self.config.global_blacklist.set(global_blacklist)
                embed = discord.Embed(title="Success!", description=f"{user.display_name} has been removed from the global wormhole blacklist.")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="ErRoR 404", description=f"{user.display_name} is not in the global wormhole blacklist.")
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description="You must be the bot owner to use this command.")
            await ctx.send(embed=embed)

    @wormhole.command(name="addwordfilter")
    async def wormhole_addwordfilter(self, ctx, *, word: str):
        """Add a word to the wormhole word filter."""
        if await self.bot.is_owner(ctx.author):
            word_filters = await self.config.word_filters()
            if word not in word_filters:
                word_filters.append(word)
                await self.config.word_filters.set(word_filters)
                embed = discord.Embed(title="Success!", description=f"`{word}` has been added to the wormhole word filter.")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="ErRoR 404", description=f"`{word}` is already in the wormhole word filter.")
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description="You must be the bot owner to use this command.")
            await ctx.send(embed=embed)

    @wormhole.command(name="removewordfilter")
    async def wormhole_removewordfilter(self, ctx, *, word: str):
        """Remove a word from the wormhole word filter."""
        if await self.bot.is_owner(ctx.author):
            word_filters = await self.config.word_filters()
            if word in word_filters:
                word_filters.remove(word)
                await self.config.word_filters.set(word_filters)
                embed = discord.Embed(title="Success!", description=f"`{word}` has been removed from the wormhole word filter.")
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="ErRoR 404", description=f"`{word}` is not in the wormhole word filter.")
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description="You must be the bot owner to use this command.")
            await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(WormHole(bot))
