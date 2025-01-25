from typing import Dict, List, Literal, Set

import discord
from redbot.core import commands, Config
from redbot.core.i18n import Translator

from notifymeon.types import ListenEventType

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

_ = Translator("NotifyMeOn", __file__)

class NotifyMeOn(commands.Cog):
    """
    DM requester on requested guild events
    """

    guild_defaults = {
        "events": {}
    }

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config: Config = Config.get_conf(
            self,
            identifier=76161837353446945617272855823381917199835369864446,
            force_registration=True,
        )

        #  Dict[ListenEventType, Set[int]] = {}
        self.config.register_guild(**self.guild_defaults)

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    @commands.guild_only()
    @commands.command()
    async def notifymeon(self, ctx: commands.Context, event_type: str):
        if not event_type in ListenEventType:
            raise TypeError("`event_type` must be one of: " + [e.value for e in ListenEventType])

        user_id = ctx.author.id
        eventType = ListenEventType[event_type]

        guildConfig = await self.config.guild(ctx.guild)

        if guildConfig.events[eventType] == None:
            guildConfig.events[eventType] = {}

        if user_id in guildConfig.events[eventType]:
            guildConfig.events[eventType].remove(user_id)
            await ctx.send(_("Will notify you on {eventType}").format(eventType=event_type))
        else:
            guildConfig.events[eventType].add(user_id)
            await ctx.send(_("Will no longer notify you on {eventType}").format(eventType=event_type))
        
        await self.config.guild(ctx.guild).set(guildConfig)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        guildConfig = await self.config.guild(entry.guild)
        if ListenEventType.ON_AUDIT_LOG_ENTRY not in guildConfig.events:
            return;

        userList = guildConfig.events[ListenEventType.ON_AUDIT_LOG_ENTRY]

        for userId in userList:
            user = entry.guild.get_member(userId)
            if user:
                await user.send(_("Detected a new log entry in {guild}").format(guild=entry.guild.name))
