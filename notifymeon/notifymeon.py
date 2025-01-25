import logging
import json

from typing import Dict, List, Literal, Optional, Set

import discord
from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.i18n import Translator

from notifymeon.types import ListenEventType

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

CHANNEL_LINK_BASE="https://discord.com/channels/"

_ = Translator("NotifyMeOn", __file__)
log = logging.getLogger("NotifyMeOn")

class NotifyMeOn(commands.Cog):
    """
    DM requester on requested guild events
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config: Config = Config.get_conf(
            self,
            identifier=76161837353446945617272855823381917199835369864446,
            force_registration=True,
        )

        self.config.register_guild(events={})
        self.guild_events: Dict[discord.Guild, Dict[ListenEventType, Set[str]]] = {}

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    async def save_config(self) -> None:
        for guild in self.guild_events:
            await self.save_config(guild)

    async def save_config(self, guild: discord.Guild) -> None:
        newConfig: Dict[str, List[str]] = {}
        for eventType in self.guild_events[guild]:
            newConfig[eventType.value] = list(self.guild_events[guild][eventType])

        await self.config.guild(guild).events.set(newConfig)

    async def load_config(self, guild: discord.Guild) -> None:
        if guild not in self.guild_events:
            guildConfig: Dict[str, List[str]] = await self.config.guild(guild).events()

            self.guild_events[guild] = {}
            for eventTypeName in guildConfig:
                self.guild_events[guild][ListenEventType(eventTypeName)] = set(guildConfig[eventTypeName])

    @commands.guild_only()
    @commands.hybrid_command()
    @app_commands.allowed_installs(guilds=True)
    # @app_commands.choices(eventType=[
    #     app_commands.Choice(name="Audit Log Entry Created Event", value=ListenEventType.ON_AUDIT_LOG_ENTRY)
    # ])
    async def notifymeon(self, ctx: commands.Context, eventType: ListenEventType) -> None:
        """Register a notification for yourself on event occurrence.

        **Event types:**
        - `audit_log_entry`: on Guild Audit Log Entry Creation

        **Examples:**
        - `[p]notifymeon audit_log_entry`
        """
        user_id = ctx.author.id
        await self.load_config(ctx.guild)
        events = self.guild_events[ctx.guild]

        if eventType not in events:
            events[eventType] = set()

        if user_id in events[eventType]:
            events[eventType].remove(user_id)
            await ctx.send(_("Will no longer notify you on any `{eventType}` events in this Guild").format(eventType=eventType.value))
        else:
            events[eventType].add(user_id)
            await ctx.send(_("Will notify you on any `{eventType}` events in this Guild").format(eventType=eventType.value))

        await self.save_config(ctx.guild)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):

        await self.load_config(entry.guild)
        events = self.guild_events[entry.guild]

        if ListenEventType.ON_AUDIT_LOG_ENTRY not in events:
            return;

        userList = events[ListenEventType.ON_AUDIT_LOG_ENTRY]

        for userId in userList:
            user: discord.Member = entry.guild.get_member(userId)
            if user:
                await user.send(embed=await self.auditLogEntryToEmbed(entry))

    async def auditLogEntryToEmbed(self, entry: discord.AuditLogEntry) -> discord.Embed:
        guild = entry.guild
        url = CHANNEL_LINK_BASE + str(guild.id)
        target = "[{caption}]({link})".format(caption=guild.name, link=url)

        if isinstance(entry.target, discord.abc.GuildChannel):
            channel = guild.get_channel(entry.target.id)
            url = channel.jump_url
            target = url

        embed = discord.Embed(title="NotifyMeOn AuditLogEntry Alert", description="Detected a new audit log entry in\n{target}".format(target=target))

        authorUser: discord.Member = guild.get_member(entry.user_id)
        if authorUser:
            embed.set_author(name=authorUser.name, icon_url=authorUser.avatar.url)

        if isinstance(entry.target, discord.Member):
            embed.add_field(name="Target", inline=False, value=entry.target.name)
        elif isinstance(entry.target, discord.User):
            embed.add_field(name="Target", inline=False, value=entry.target.name)
        elif isinstance(entry.target, discord.Role):
            embed.add_field(name="Target", inline=False, value=entry.target.name)

        embed.add_field(name="Action", inline=False, value=entry.action.name)

        if entry.changes:
            change_attrs = [attr for attr in dir(entry.before) if not attr.startswith('__')]
            for attr in change_attrs:
                embed.add_field(name=attr, inline=False, value="`{before}`\n`{after}`".format(
                    before=getattr(entry.before, attr),
                    after=getattr(entry.after, attr)
                ))

        return embed