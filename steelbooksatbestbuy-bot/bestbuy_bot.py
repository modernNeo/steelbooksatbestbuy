import asyncio
import datetime
import os
import re
from typing import Optional, List

import django
import requests
from asgiref.sync import sync_to_async
from discord import Role
from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument, CheckFailure, Context
from django.db.models import QuerySet

bot = commands.Bot(command_prefix='.')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from steelbooksatbestbuy.models import Media, Alert, User, LastTimeAlertWasUsedForSpecificMedia, Guild, \
    RoleToTargetForGuild


@bot.event
async def on_ready():
    print('Logged in as')
    print(f'{bot.user.name}')
    print(f'{bot.user.id}')
    print('------')
    print(f"{bot.user.name} is now ready for commands")


def check_is_owner(ctx: Context):
    return ctx.author.guild.owner_id == ctx.author.id


class BestBuyBot(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "DNT": "1",
            "Host": "www.bestbuy.ca",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0"
        }

    @commands.command(help='saves email so the bot can email you the notification in addition to discord DMs')
    async def save_email(self, ctx: Context, email: str):
        print(f"saving email for user {ctx.author.id}")
        await ctx.message.delete()
        email = email.strip().lower()
        error_message = await self._save_email(ctx.author.id, email)
        if error_message is not None:
            await ctx.send(error_message)
            return
        await ctx.send("Your email has been saved")

    @sync_to_async
    def _save_email(self, discord_id: int, email: str) -> Optional[str]:
        print(f"saving email for discord id {discord_id}")
        if not re.match(r"^\w+@(gmail|hotmail|protonmail|sfu|outlook|icloud|me)\.(com|ca)+$", email):
            return "Invalid email detected"
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            people_to_alert = User(discord_id=discord_id)
        people_to_alert.email = email
        people_to_alert.save()
        return None

    @commands.command(help="clears your email from the system")
    async def clear_email(self, ctx: Context):
        print(f"clearing email for user {ctx.author.id}")
        await self._clear_email(ctx.author.id)
        await ctx.send("Your email has been deleted")

    @sync_to_async
    def _clear_email(self, discord_id: int):
        print(f"deleting email for discord id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            return
        people_to_alert.email = None
        people_to_alert.save()

    @commands.command(help='saves phone number so the bot can text you the notification in addition to discord DMs')
    async def save_number(self, ctx: Context, phone_number: str):
        print(f"saving number for user {ctx.author.id}")
        await ctx.message.delete()
        await self._save_number(ctx.author.id, phone_number)
        await ctx.send("Your number has been saved")

    @sync_to_async
    def _save_number(self, discord_id: int, phone_number: str):
        print(f"saving phone_number {phone_number} for discord id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            people_to_alert = User(discord_id=discord_id)
        people_to_alert.phone_number = phone_number
        people_to_alert.save()

    @commands.command(help="clears your number from the system")
    async def clear_number(self, ctx: Context):
        print(f"clearing email for user {ctx.author.id}")
        await self._clear_number(ctx.author.id)
        await ctx.send("Your number has been deleted")

    @sync_to_async
    def _clear_number(self, discord_id: int):
        print(f"deleting sms for discord id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            return
        people_to_alert.phone_number = None
        people_to_alert.save()

    @commands.command(
        help="add an item to the list of items you will get alerted to when its ready from bestbuy.ca")
    async def alert_me(self, ctx: Context, *media_name):
        media_name = (" ".join(media_name)).strip().lower()
        print(f"saving \"{media_name}\" alert item for user {ctx.author.id}")
        await self._save_alert(ctx.author.id, media_name)
        await ctx.send(f"You will be notified when {media_name} is available to purchase from bestbuy.ca")
        number_of_medias, medias, date_for_updates_to_ignore = await self._get_latest_medias()
        print(number_of_medias)
        if len(medias) > 0:
            await self._alert_users_of_positive_matches(
                medias=medias, date_for_updates_to_ignore=date_for_updates_to_ignore, discord_id=ctx.author.id
            )

    @sync_to_async
    def _save_alert(self, discord_id: int, media_name: str):
        print(f"saving search for {media_name} for discord_id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            people_to_alert = User(discord_id=discord_id)
            people_to_alert.save()
        alert_obj = Alert(person_to_alert=people_to_alert, media_search_string=media_name)
        alert_obj.save()

    @sync_to_async
    def _get_latest_medias(self, limit_search_to_new_media: bool = False) -> tuple[int, List[Media], datetime.datetime]:
        date_for_updates_to_ignore = datetime.datetime.now()
        medias = Media.objects.all().filter(
            needs_to_be_processed_by_bot=True
        ) if limit_search_to_new_media else Media.objects.all()
        if limit_search_to_new_media:
            for media in medias:
                media.needs_to_be_processed_by_bot = False
            date_for_updates_to_ignore = datetime.datetime.now()
            Media.objects.bulk_update(medias, ['needs_to_be_processed_by_bot'])
        else:
            order_able_skus = [media.sku for media in medias if media.order_able]
            medias = medias.filter(sku__in=order_able_skus)
        return len(medias), medias, date_for_updates_to_ignore

    @sync_to_async
    def _alert_users_of_positive_matches(self, medias: QuerySet[Media], date_for_updates_to_ignore: datetime.datetime,
                                         discord_id: int = None):

        alerts = Alert.objects.all() \
            if discord_id is None \
            else Alert.objects.all().filter(person_to_alert__discord_id=discord_id)

        for alert in alerts:
            print(f"processing alert {alert} for user {discord_id}")
            match_media_for_alert = []
            latest_times_alert_was_used_for_specific_medias = \
                LastTimeAlertWasUsedForSpecificMedia.objects.all().filter(
                    alert=alert
                )
            for matching_media in medias.filter(sku__in=self._get_matching_skus(alert.media_search_string)):
                print(f"processing media {matching_media} for alert {alert}")
                latest_time_alert_was_used_for_specific_media = \
                    latest_times_alert_was_used_for_specific_medias.filter(
                        media=matching_media
                    ).order_by('-date_for_updates_to_ignore').first()
                if latest_time_alert_was_used_for_specific_media is None:
                    # first time that this alert is being used for this item
                    media_was_updated_after_ignore_mapping = True
                else:
                    media_was_updated_after_ignore_mapping = latest_time_alert_was_used_for_specific_media.date_for_updates_to_ignore < matching_media.get_latest_quantity().date
                print(
                    f"order can{'' if matching_media.get_latest_quantity().order_can_be_placed() else 'not'} be placed"
                    f" for {matching_media}"
                )
                print(
                    f" media was {'' if media_was_updated_after_ignore_mapping else 'not '}updated after ignore "
                    f"mapping was set for {matching_media}"
                )
                if matching_media.get_latest_quantity().order_can_be_placed() and media_was_updated_after_ignore_mapping:
                    match_media_for_alert.append(matching_media)

            for matching_media in match_media_for_alert:
                BestBuyBot._send_alerts(alert, matching_media, date_for_updates_to_ignore)
        print("found and alerted users to all relevant medias")

    def _get_matching_skus(self, search_string: str) -> list[str]:
        response = requests.get(
            f"https://www.bestbuy.ca/api/v2/json/search?categoryid=&currentRegion=ON&include=facets,"
            f"redirects&lang=en-CA&page=1&pageSize=24&path=&query={search_string}&exp=&sortBy=relevance"
            f"&sortDir=desc",
            headers=self.headers
        )
        return [product['sku'] for product in response.json()['products']]

    @staticmethod
    def _send_alerts(alert: Alert, media: Media, date_for_updates_to_ignore: datetime.datetime):
        media_that_alert_has_to_ignore = LastTimeAlertWasUsedForSpecificMedia.objects.all().filter(
            alert=alert, media=media
        ).first()
        if media_that_alert_has_to_ignore is None:
            media_that_alert_has_to_ignore = LastTimeAlertWasUsedForSpecificMedia(
                alert=alert, media=media
            )
        media_that_alert_has_to_ignore.date_for_updates_to_ignore = date_for_updates_to_ignore
        media_that_alert_has_to_ignore.save()
        if alert.person_to_alert.discord_id != 0:
            alert.person_to_alert.send_discord_dm(
                media, alert.media_search_string
            )
        if alert.person_to_alert.email is not None:
            alert.person_to_alert.send_email(media.name, media.product_url)
        if alert.person_to_alert.phone_number is not None:
            alert.person_to_alert.send_sms(media.name, media.product_url)
        print(f"all enabled alerts sent to {alert.person_to_alert.discord_id}")

    @commands.command(help="List all alerts")
    async def alerts(self, ctx: Context):
        print(f"getting notifications for user {ctx.author.id}")
        message = ""
        person_to_alert = await self._get_user_by_discord_id(ctx.author.id)
        if person_to_alert is not None:
            message += "ID - Media Name\n"
            for alert in await self._get_alerts_by_discord_id(person_to_alert):
                message += f"{alert.id} - {alert.media_search_string}\n"
        message += "\n\nNotification Settings:"
        if person_to_alert is None:
            message += " None Set"
        else:
            message += " Discord ID"
            notification_setting_already_printed = True
            if person_to_alert.email is not None:
                if notification_setting_already_printed is True:
                    message += " |"
                message += " Email"
                notification_setting_already_printed = True
            if person_to_alert.phone_number is not None:
                if notification_setting_already_printed:
                    message += " |"
                message += " Text"
        await ctx.send(message)

    @sync_to_async
    def _get_user_by_discord_id(self, discord_id: int) -> User:
        return User.objects.all().filter(discord_id=discord_id).first()

    @sync_to_async
    def _get_alerts_by_discord_id(self, person_to_alert: User) -> List[Alert]:
        return list(person_to_alert.alert_set.all())

    @commands.command(help="removes an item from the list of items you will get alerted about")
    async def remove_alert(self, ctx: Context, alert_id: int):
        print(f"removing alert item {alert_id} for {ctx.author.id}")
        await self._remove_alert(ctx.author.id, alert_id)
        await ctx.send(f"Notification with ID {alert_id} removed")

    @sync_to_async
    def _remove_alert(self, discord_id: int, alert_id: int):
        media_alert = Alert.objects.all().filter(
            person_to_alert__discord_id=discord_id, id=alert_id
        ).first()
        if media_alert is not None:
            media_alert.delete()

    @commands.command(help="Removes all your alerts")
    async def remove_alerts(self, ctx: Context):
        print(f"removing all alerts for {ctx.author.id}")
        await self._remove_alerts(ctx.author.id)
        await ctx.send("All your notifications have beem removed")

    @sync_to_async
    def _remove_alerts(self, discord_id: int):
        Alert.objects.all().filter(person_to_alert__discord_id=discord_id).delete()

    @commands.command(help="Clear any information associated with you from the bot")
    async def clear_data(self, ctx: Context):
        print(f"clearing all data for {ctx.author.id}")
        await self._clear_user_data(ctx.author.id)
        await ctx.send("Your data and alerts has been wiped.")

    @sync_to_async
    def _clear_user_data(self, discord_id: int):
        User.objects.all().filter(discord_id=discord_id).delete()

    @commands.command(help="Get the url for the website which shows all current steelbooks")
    async def steelbooks(self, ctx: Context):
        await ctx.send("http://127.0.0.1:8000")

    @commands.command(help="Save channel for alerts to be sent on")
    @commands.check(check_is_owner)
    async def save_channel(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if len(ctx.message.channel_mentions) > 0:
            mentioned_channel = ctx.message.channel_mentions[0]
            if guild_obj is None:
                guild_obj = Guild(
                    guild_id=ctx.guild.id, guild_name=ctx.guild.name, channel_name=mentioned_channel.name,
                    channel_id=mentioned_channel.id
                )
            await self._set_channel_for_guild(guild_obj)
            await ctx.send(f"Channel set to {guild_obj.channel_name}")
        else:
            await ctx.send(f"No channel mentioned in command")

    @sync_to_async
    def _get_guild_by_id(self, guild_id: int) -> Guild:
        return Guild.objects.all().filter(guild_id=guild_id).first()

    @sync_to_async
    def _set_channel_for_guild(self, guild_obj: Guild):
        guild_obj.save()

    @commands.command(help="clear channel for alerts to be sent on")
    @commands.check(check_is_owner)
    async def clear_channel(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is not None:
            await self.clear_channel_for_guild(guild_obj)

    @sync_to_async
    def clear_channel_for_guild(self, guild_obj: Guild):
        guild_obj.delete()

    @commands.command(help="List channel for alerts to be sent on")
    @commands.check(check_is_owner)
    async def channel(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is not None:
            await ctx.send(f"Channel set to {guild_obj.channel_name}")
        else:
            await ctx.send("No Channel set to alerts")

    @commands.command(help="Add a role that has to be tagged")
    @commands.check(check_is_owner)
    async def add_role_tag(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        if len(ctx.message.role_mentions) > 0:
            mentioned_role = ctx.message.role_mentions[0]
            role_to_target_for_guild = await self._get_role_to_targ_by_name(role_to_tag_name=mentioned_role.name)
            await self._save_role_to_tag(guild_obj, mentioned_role.name, mentioned_role, role_to_target_for_guild)
            await ctx.send(f"Role \"{mentioned_role.name}\" will be tagged")
        else:
            await ctx.send(f"No role was mentioned")

    @sync_to_async
    def _get_role_to_targ_by_name(self, role_to_tag_name: int) -> RoleToTargetForGuild:
        return RoleToTargetForGuild.objects.all().filter(role_to_tag_name=role_to_tag_name).first()

    @sync_to_async
    def _save_role_to_tag(
        self, guild_obj: Guild, role_to_tag_name: str, role: Role, role_to_target_for_guild: RoleToTargetForGuild = None
    ):
        if role_to_target_for_guild is None:
            RoleToTargetForGuild(
                guild=guild_obj,
                role_to_tag_name=role_to_tag_name,
                role_to_tag_id=role.id
            ).save()
        else:
            role_to_target_for_guild.role_to_tag_id = role.id
            role_to_target_for_guild.save()

    @commands.command(help="List roles to tag for alerts")
    @commands.check(check_is_owner)
    async def role_tags(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        roles_to_tag = await self._get_roles_to_tag_by_guild_id(guild_obj.guild_id)
        if len(roles_to_tag) > 0:
            message = f"Roles that will be tagged:\n"
            for role_to_tag in roles_to_tag:
                message += f"{role_to_tag.role_to_tag_name}\n"
            await ctx.send(message)
        else:
            await ctx.send(f"No role are set to be tagged")

    @sync_to_async
    def _get_roles_to_tag_by_guild_id(self, guild_id: int) -> List[Role]:
        return list(RoleToTargetForGuild.objects.all().filter(guild__guild_id=guild_id))

    @commands.command(help="Stop a role from being tagged")
    @commands.check(check_is_owner)
    async def remove_role_tag(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        if len(ctx.message.role_mentions) > 0:
            mentioned_role = ctx.message.role_mentions[0]
            await self._delete_role_to_tag_by_name(mentioned_role.name)
            await ctx.send(f"Role \"{mentioned_role.name}\" will no longer be tagged")
        else:
            await ctx.send(f"No role was mentioned")

    @sync_to_async
    def _delete_role_to_tag_by_name(self, role_to_tag_name: int):
        role_to_tag = RoleToTargetForGuild.objects.all().filter(role_to_tag_name=role_to_tag_name).first()
        if role_to_tag is not None:
            role_to_tag.delete()

    @commands.command(help="Stop tagging all roles")
    @commands.check(check_is_owner)
    async def remove_role_tags(self, ctx: Context):
        guild_obj = await self._get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        await self._delete_tag_roles_in_guild(guild_obj.guild_id)
        await ctx.send(f"All tagged roles for this guild have been removed")

    @sync_to_async
    def _delete_tag_roles_in_guild(self, guild_id: int = None):
        RoleToTargetForGuild.objects.all().filter(guild_id=guild_id).delete()

    @commands.Cog.listener(name='on_ready')
    async def alert_users_once_an_hour(self):
        while True:
            now = datetime.datetime.now()
            if now.minute == 0:
                print(f"time to alert the users and guilds on the hour at {now}")
                number_of_medias, medias, date_for_updates_to_ignore = await self._get_latest_medias(
                    limit_search_to_new_media=True
                )
                print(f"got {number_of_medias} medias that the guilds and users have to be alerted about")
                if number_of_medias > 0:
                    await self.send_alert_to_guilds(medias)
                    users = await self.get_all_users()
                    print(f"got {len(users)} users to notify")
                    for user in users:
                        await self._alert_users_of_positive_matches(
                            medias, date_for_updates_to_ignore, discord_id=user.discord_id
                        )
            await asyncio.sleep(60)

    @sync_to_async
    def send_alert_to_guilds(self, medias: List[Media]):
        guild_objs = Guild.objects.all()
        print(f"got {len(guild_objs)} guild objects to report about {len(medias)} medias")
        guild_ids = [guild_obj.guild_id for guild_obj in guild_objs]
        matching_guilds = [guild for guild in self.bot.guilds if guild.id in guild_ids]
        print(f"got {len(matching_guilds)} matching guild objects to report about {len(medias)} medias")

        guild_map = {
            guild_obj.guild_id: guild_obj
            for guild_obj in guild_objs
        }
        for matching_guild in matching_guilds:
            channel_id = guild_map[matching_guild.id].channel_id
            channel_name = guild_map[matching_guild.id].channel_name
            channel_matching_by_id = False
            channel_matching_by_name = None
            for channel in matching_guild.text_channels:
                if channel.id == channel_id:
                    channel_matching_by_id = True
                    print(f"got a channel [{channel_id}] to match by ID")
                    break
                if channel.name == channel_name:
                    channel_matching_by_name = channel
                    print(f"got a channel [{channel_name}] to match by name")
            print(
                f"got channel_matching_by_id=[{channel_matching_by_id}] and "
                f"channel_matching_by_name=[{channel_matching_by_name}]"
            )
            roles = guild_map[matching_guild.id].roletotargetforguild_set.all()
            if channel_matching_by_id:
                for media in medias:
                    guild_map[matching_guild.id].send_alert(roles, channel_id, media)
            elif channel_matching_by_name is not None:
                for media in medias:
                    guild_map[matching_guild.id].send_alert(roles, channel_matching_by_name.id, media)

    @sync_to_async
    def get_all_users(self) -> list[User]:
        return list(User.objects.all())

    @commands.Cog.listener(name="on_command_error")
    async def error(self, ctx: Context, error: CheckFailure):
        if isinstance(error, MissingRequiredArgument) or isinstance(error, CheckFailure):
            await ctx.send(f"{error}")


# put on https://steelbooksatbestbuy.ca


bot.add_cog(BestBuyBot(bot))
bot.run(os.environ["TOKEN"])
