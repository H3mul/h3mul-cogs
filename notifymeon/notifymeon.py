import logging

from typing import Dict, List, Literal, Optional, Set, Tuple

import discord
from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.i18n import Translator

from notifymeon.types import ListenEventType, FilterType

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

        self.config.register_guild(events={}, filters={})

        # guild : eventType : Set(userId)
        self.guild_events: Dict[discord.Guild, Dict[ListenEventType, Set[int]]] = {}
        # guild : userId: eventType : filterType: Set(filterStr)
        self.filters: Dict[discord.Guild, Dict[int, Dict[FilterType, Set[str]]]] = {}

    async def red_delete_data_for_user(self, *, requester: RequestType, user_id: int) -> None:
        # TODO: Replace this with the proper end user data removal handling.
        super().red_delete_data_for_user(requester=requester, user_id=user_id)

    async def save_config(self) -> None:
        for guild in self.guild_events:
            await self.save_config(guild)

    async def save_config(self, guild: discord.Guild) -> None:
        newEvents: Dict[str, List[int]] = {}
        for eventType in self.guild_events[guild]:
            newEvents[eventType.value] = list(self.guild_events[guild][eventType])
        await self.config.guild(guild).events.set(newEvents)

        newFilters: Dict[int, Dict[str, List[str]]] = {}
        for (user_id, eventDict) in self.filters[guild].items():
            newFilters[user_id] = {}
            for (eventType, filterDict) in eventDict.items():
                newFilters[user_id][eventType.value] = {}
                for (filterType, filterSet) in filterDict.items():
                    newFilters[user_id][eventType.value][filterType.value] = list(filterSet)
        await self.config.guild(guild).filters.set(newFilters)

    async def load_config(self, guild: discord.Guild) -> None:
        if guild not in self.guild_events:
            guildConfig: Dict[str, List[str]] = await self.config.guild(guild).events()

            self.guild_events[guild] = {}
            for eventTypeName in guildConfig:
                self.guild_events[guild][ListenEventType(eventTypeName.replace('_', ''))] = set(guildConfig[eventTypeName])

        if guild not in self.filters:
            filterConfig: Dict[int, Dict[str, List[str]]] = await self.config.guild(guild).filters()

            self.filters[guild] = {}
            for (user_id_str, eventDict) in filterConfig.items():
                user_id = int(user_id_str)
                self.filters[guild][user_id] = {}
                for (eventTypeStr, filterDict) in eventDict.items():
                    eventType = ListenEventType(eventTypeStr.replace('_', ''))
                    self.filters[guild][user_id][eventType] = {}
                    for (filterTypeStr, filterList) in filterDict.items():
                        filterType = FilterType(filterTypeStr.replace('_', ''))
                        self.filters[guild][user_id][eventType][filterType] = set(filterList)

        return (self.guild_events[guild], self.filters[guild])

    @commands.guild_only()
    @commands.hybrid_group()
    @app_commands.allowed_installs(guilds=True)
    async def notifymeon(self, ctx: commands.Context) -> None:
        """ Handle event notifications
        
        Will DM you on any matching event occurrence
        """
        pass

    @notifymeon.command(name="showconfig")
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True)
    async def list_user_settings(self, ctx: commands.Context) -> None:
        """ List current user preferences """
        (events, filters) = await self.load_config(ctx.guild)
        user_id = ctx.author.id

        typeList = ",".join([ eventType.value for (eventType, users) in events.items() if user_id in users ])
        await ctx.send(_("Currently listening to events:\n`{typeList}`").format(typeList=typeList))

        if user_id in filters:
            userFilters = filters[user_id]

            filterStr = ""
            for (eventType, filterDict) in userFilters.items():
                for (filterType, filterSet) in filterDict.items():
                    if len(filterSet) > 0:
                        filterStr += "\n- `{filterType}`: `[{filterList}]`".format(filterType=filterType.value, filterList=",".join(filterSet))  

                if filterStr:
                    filterStr = "  `{eventType}`:".format(eventType=eventType.value) + filterStr
        
            if filterStr:
                await ctx.send(_("Currently filtering events:\n{filterStr}").format(filterStr=filterStr))

    @notifymeon.group(invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator = True)
    @app_commands.allowed_installs(guilds=True)
    async def auditlogentry(self, ctx: commands.Context) -> None:
        """ Notify on audit log entry  _([p]help for more)_ """
        await self._register_event_notification(ctx, ListenEventType.ON_AUDIT_LOG_ENTRY)

    async def _register_event_notification(self, ctx: commands.Context, eventType: ListenEventType) -> None:
        user_id = ctx.author.id
        (events, __) = await self.load_config(ctx.guild)

        if eventType not in events:
            events[eventType] = set()

        if user_id in events[eventType]:
            events[eventType].remove(user_id)
            await ctx.send(_("Will no longer notify you on any `{eventType}` events in this Guild").format(eventType=eventType.value))
        else:
            events[eventType].add(user_id)
            await ctx.send(_("Will notify you on any `{eventType}` events in this Guild").format(eventType=eventType.value))

        await self.save_config(ctx.guild)

    @auditlogentry.command()
    @commands.guild_only()
    @commands.has_permissions(administrator = True)
    @app_commands.allowed_installs(guilds=True)
    async def filteraction(self, ctx: commands.Context, auditlogaction: str) -> None:
        """Filter audit log entry from notifications by action type"""
        user_id = ctx.author.id

        (__, filters) = await self.load_config(ctx.guild)

        if user_id not in filters:
            filters[user_id] = {}
        
        if ListenEventType.ON_AUDIT_LOG_ENTRY not in filters[user_id]:
            filters[user_id][ListenEventType.ON_AUDIT_LOG_ENTRY] = {}

        auditLogFilters = filters[user_id][ListenEventType.ON_AUDIT_LOG_ENTRY]

        if FilterType.BLACKLIST not in auditLogFilters:
            auditLogFilters[FilterType.BLACKLIST] = set([auditlogaction])
            await ctx.send(_("Silencing auditlogentry action `{action}` from notifications in this Guild").format(action=auditlogaction))
        elif auditlogaction in auditLogFilters[FilterType.BLACKLIST]:
            auditLogFilters[FilterType.BLACKLIST].remove(auditlogaction)
            await ctx.send(_("Removing the filter on auditlogentry action `{action}`, will notify on them in this Guild").format(action=auditlogaction))
        else:
            auditLogFilters[FilterType.BLACKLIST].add(auditlogaction)
            await ctx.send(_("Silencing auditlogentry action `{action}` from notifications in this Guild").format(action=auditlogaction))
        await self.save_config(ctx.guild)

    @auditlogentry.command()
    @commands.guild_only()
    @commands.has_permissions(administrator = True)
    @app_commands.allowed_installs(guilds=True)
    async def replay(self, ctx: commands.Context, num: int = 1) -> None:
        """Replay last n audit log notifications (test)"""
        limit = max(min(num, 50), 1)
        async for entry in ctx.guild.audit_logs(limit=limit):
            await ctx.author.send(embed=await self.auditLogEntryToEmbed(entry))

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        (events, filters) = await self.load_config(entry.guild)

        if ListenEventType.ON_AUDIT_LOG_ENTRY not in events:
            return;

        userList = events[ListenEventType.ON_AUDIT_LOG_ENTRY]

        for userId in userList:
            user: discord.Member = entry.guild.get_member(userId)
            if user:
                userFilters = filters[user.id]
                if not (user.id in filters and 
                        ListenEventType.ON_AUDIT_LOG_ENTRY in userFilters and 
                        entry.action.name in userFilters[ListenEventType.ON_AUDIT_LOG_ENTRY][FilterType.BLACKLIST]):
                    await user.send(embed=await self.auditLogEntryToEmbed(entry))

    async def auditLogEntryToEmbed(self, entry: discord.AuditLogEntry) -> discord.Embed:
        guild = entry.guild
        url = CHANNEL_LINK_BASE + str(guild.id)
        target = "[{caption}]({link})".format(caption=guild.name, link=url)

        if isinstance(entry.target, discord.abc.GuildChannel):
            channel = guild.get_channel(entry.target.id)
            url = channel.jump_url
            target = url

        embed = discord.Embed(title=_("NotifyMeOn AuditLogEntry Alert"), description=_("Detected a new audit log entry in\n{target}").format(target=target))

        authorUser: discord.Member = guild.get_member(entry.user_id)
        if authorUser:
            embed.set_author(name=authorUser.name, icon_url=authorUser.avatar.url)

        embed.add_field(name=_("Target"), inline=True, value=self.printDiscordObject(entry.target))
        embed.add_field(name=_("Action"), inline=True, value=entry.action.name)

        if entry.extra:
            extra = ""
            if isinstance(entry.extra, discord.audit_logs._AuditLogProxy):
                embed.add_field(name=_("Extra"), inline=False, value=self.printAttributes(entry.extra))
            else:
                embed.add_field(name=_("Extra"), inline=True, value=self.printDiscordObject(entry.extra))

        if entry.after:
            for (attr, afterValue) in entry.after:
                beforeValue = getattr(entry.before, attr)

                result = afterValue
                if isinstance(afterValue, list):
                    result = self.printIterableChange(beforeValue, afterValue)
                elif isinstance(afterValue, discord.Permissions):
                    result = self.printPermissionsChange(beforeValue, afterValue)
                embed.add_field(name=attr, inline=True, value=self.printDiscordObject(result))

        return embed

    def printAttributes(self, target: any) -> str:
        values = ["_{name}:_ {value}".format(name=attr, value=self.printDiscordObject(getattr(target,attr))) for attr in dir(target) if not attr.startswith('__') ]
        return "\n".join(values)

    def printDiscordObject(self, target: discord.Object) -> str:
        # if hasattr(target, '__iter__'):
        #     return "\n - ".join([self.printDiscordObject(item) for item in target])
        if hasattr(target, "name"):
            return "{name}: **{value}**".format(name=target.__class__.__name__, value=target.name)
        return str(target)

    def printPermissionsChange(self, before: discord.Permissions, after: discord.Permissions) -> str:
        permChanges = []
        for (attr, value) in after:
            if getattr(before, attr) != value:
                permChanges.append("`{sign} {attr}`".format(attr=attr, sign="+" if value else "-"))
        return "\n".join(permChanges)
    
    def printIterableChange(self, before: List[any], after: List[any]):
        listChanges = []
        for item in set(before) - set(after):
            listChanges.append("`-` {value}".format(value=self.printDiscordObject(item)))
        for item in set(after) - set(before):
            listChanges.append("`+` {value}".format(value=self.printDiscordObject(item)))
        return "\n".join(listChanges)