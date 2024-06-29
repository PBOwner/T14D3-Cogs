import discord
import os
from redbot.core import commands, Config
from datetime import datetime, timedelta
import re

class WormHole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="wormhole", force_registration=True)
        self.config.register_global(
            linked_channels_list=[],
            global_blacklist=[],
            word_filters=[],
            mention_bypass_users=[]
        )  # Initialize the configuration
        self.message_references = {}  # Store message references
        self.relayed_messages = {}  # Store relayed messages
        self.user_ping_count = {}  # Track user pings

    async def send_status_message(self, message, channel, title):
        linked_channels = await self.config.linked_channels_list()
        guild = channel.guild
        embed = discord.Embed(title=title, description=f"{guild.name}: {message}")
        for channel_id in linked_channels:
            relay_channel = self.bot.get_channel(channel_id)
            if relay_channel and relay_channel != channel:
                await relay_channel.send(embed=embed)

    @commands.group(name="wormhole", aliases=["wm"], invoke_without_command=True)
    async def wormhole(self, ctx):
        """Manage wormhole connections."""
        await ctx.send_help(ctx.command)

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

    @wormhole.command(name="ownerclose")
    @commands.is_owner()
    async def wormhole_ownerclose(self, ctx, channel_id: int):
        """Forcibly close a connection to the wormhole (Bot Owner Only)."""
        linked_channels = await self.config.linked_channels_list()
        if channel_id in linked_channels:
            linked_channels.remove(channel_id)
            await self.config.linked_channels_list.set(linked_channels)
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(title="Success!", description=f"The channel {channel.mention} (ID: {channel_id}) has been forcibly severed from the wormhole.")
                await ctx.send(embed=embed)
                await self.send_status_message(f"The signal from {channel.mention} has been forcibly severed by the bot owner.", channel, "Success!")
            else:
                embed = discord.Embed(title="Success!", description=f"The channel ID {channel_id} has been forcibly severed from the wormhole.")
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description=f"The channel ID {channel_id} is not part of the wormhole.")
            await ctx.send(embed=embed)

    @wormhole.command(name="servers")
    async def wormhole_servers(self, ctx):
        """List all servers connected to the wormhole."""
        linked_channels = await self.config.linked_channels_list()
        if not linked_channels:
            await ctx.send(embed=discord.Embed(title="Wormhole Servers", description="No channels are currently linked to the wormhole.", color=discord.Color.red()))
            return

        server_list = {}
        for channel_id in linked_channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                guild = channel.guild
                if guild not in server_list:
                    server_list[guild] = []
                server_list[guild].append(channel)

        if not server_list:
            await ctx.send(embed=discord.Embed(title="Wormhole Servers", description="No servers are currently linked to the wormhole.", color=discord.Color.red()))
            return

        embed = discord.Embed(title="Connected Servers", color=discord.Color.blue())
        description = ""
        for guild, channels in server_list.items():
            owner = guild.owner
            for channel in channels:
                description += (
                    f"**{guild.name}**\n"
                    f"Owner: {owner} (ID: {owner.id})\n"
                    f"Server ID: {guild.id}\n"
                    f"Channel: {channel.mention} (ID: {channel.id})\n\n"
                )
                if len(description) > 1800:  # Ensure we don't exceed Discord's embed limit
                    embed.description = description
                    await ctx.send(embed=embed)
                    embed = discord.Embed(title="Connected Servers", color=discord.Color.blue())
                    description = ""

        if description:  # Send any remaining data
            embed.description = description
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:  # Don't allow in DMs
            return
        if message.author.bot or not message.channel.permissions_for(message.guild.me).send_messages:
            return

        linked_channels = await self.config.linked_channels_list()

        if message.channel.id in linked_channels:
            global_blacklist = await self.config.global_blacklist()
            word_filters = await self.config.word_filters()

            if message.author.id in global_blacklist:
                return  # Author is globally blacklisted

            if any(word in message.content for word in word_filters):
                embed = discord.Embed(title="ErRoR 404", description="That word is not allowed.")
                await message.channel.send(embed=embed)
                await message.delete()  # Message contains a filtered word, notify user and delete it
                return

            # Block messages containing invites
            if re.search(r"(discord\.gg/|discordapp\.com/invite/|discord\.me/|discord\.li/)", message.content):
                embed = discord.Embed(title="ErRoR 404", description="Invites are not allowed.")
                await message.channel.send(embed=embed)
                await message.delete()
                return

            display_name = message.author.display_name if message.author.display_name else message.author.name

            # Store the message reference
            self.message_references[message.id] = (message.author.id, message.guild.id)

            # Relay the message to other linked channels, removing mentions
            content = message.content

            # Remove @everyone and @here mentions
            content = content.replace("@everyone", "").replace("@here", "")

            # Handle mentions
            mentioned_users = message.mentions
            mentioned_roles = message.role_mentions

            for user in mentioned_users:
                content = content.replace(f"<@{user.id}>", '')  # Remove the mention
            for role in mentioned_roles:
                content = content.replace(f"<@&{role.id}>", '')  # Remove the role mention

            if not content.strip() and not message.attachments:  # If the message is now empty and has no attachments, delete it
                await message.delete()
                return

            # Handle emojis
            content = self.replace_emojis_with_urls(message.guild, content)

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

            # Remove @everyone and @here mentions
            content = content.replace("@everyone", "").replace("@here", "")

            # Handle mentions
            mentioned_users = after.mentions
            mentioned_roles = after.role_mentions

            for user in mentioned_users:
                content = content.replace(f"<@{user.id}>", '')  # Remove the mention
            for role in mentioned_roles:
                content = content.replace(f"<@&{role.id}>", '')  # Remove the role mention

            if any(word in content for word in await self.config.word_filters()):
                embed = discord.Embed(title="ErRoR 404", description="That word is not allowed.")
                await after.channel.send(embed=embed)
                await after.delete()  # Message contains a filtered word, notify user and delete it
                return

            if not content.strip() and not after.attachments:  # If the message is now empty and has no attachments, delete it
                await after.delete()
                return

            # Handle emojis
            content = self.replace_emojis_with_urls(after.guild, content)

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
                        try:
                            relay_message = await channel.fetch_message(relay_message_id)
                            await relay_message.delete()
                        except discord.NotFound:
                            pass  # Message is already deleted

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        linked_channels = await self.config.linked_channels_list()
        # Delete all messages from the banned user in linked channels
        for channel_id in linked_channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                async for message in channel.history(limit=1000):
                    if message.author.id == user.id:
                        await message.delete()

    def replace_emojis_with_urls(self, guild, content):
        for emoji in guild.emojis:
            if str(emoji) in content:
                content = content.replace(str(emoji), str(emoji.url))
        return content

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

    @wormhole.command(name="addmentionbypass")
    @commands.is_owner()
    async def wormhole_addmentionbypass(self, ctx, user: discord.User):
        """Allow a user to bypass the mention filter."""
        mention_bypass_users = await self.config.mention_bypass_users()
        if user.id not in mention_bypass_users:
            mention_bypass_users.append(user.id)
            await self.config.mention_bypass_users.set(mention_bypass_users)
            embed = discord.Embed(title="Success!", description=f"{user.display_name} has been allowed to bypass the mention filter.")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description=f"{user.display_name} is already allowed to bypass the mention filter.")
            await ctx.send(embed=embed)

    @wormhole.command(name="removementionbypass")
    @commands.is_owner()
    async def wormhole_removementionbypass(self, ctx, user: discord.User):
        """Remove a user's bypass for the mention filter."""
        mention_bypass_users = await self.config.mention_bypass_users()
        if user.id in mention_bypass_users:
            mention_bypass_users.remove(user.id)
            await self.config.mention_bypass_users.set(mention_bypass_users)
            embed = discord.Embed(title="Success!", description=f"{user.display_name} is no longer allowed to bypass the mention filter.")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="ErRoR 404", description=f"{user.display_name} is not allowed to bypass the mention filter.")
            await ctx.send(embed=embed)
