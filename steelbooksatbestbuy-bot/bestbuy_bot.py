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
        error_message = await self.save_email_address(ctx.author.id, email)
        if error_message is not None:
            await ctx.send(error_message)
            return
        await ctx.send("Your email has been saved")

    @commands.command(help="clears your email from the system")
    async def clear_email(self, ctx: Context):
        print(f"clearing email for user {ctx.author.id}")
        await self.clear_email_address(ctx.author.id)
        await ctx.send("Your email has been deleted")

    @commands.command(help='saves phone number so the bot can text you the notification in addition to discord DMs')
    async def save_number(self, ctx: Context, phone_number: str):
        print(f"saving number for user {ctx.author.id}")
        await ctx.message.delete()
        await self.save_phone_number(ctx.author.id, phone_number)
        await ctx.send("Your number has been saved")

    @commands.command(help="clears your number from the system")
    async def clear_number(self, ctx: Context):
        print(f"clearing email for user {ctx.author.id}")
        await self.clear_phone_number(ctx.author.id)
        await ctx.send("Your number has been deleted")

    @commands.command(
        help="add an item to the list of items you will get alerted to when its ready from bestbuy.ca")
    async def alert_me(self, ctx: Context, *media_name):
        media_name = (" ".join(media_name)).strip().lower()
        print(f"saving \"{media_name}\" alert item for user {ctx.author.id}")
        await self.save_to_alerts(ctx.author.id, media_name)
        number_of_medias, medias, date_for_updates_to_ignore = await self.get_latest_medias()
        if number_of_medias > 0:
            await self.alert_users_of_positive_matches(
                medias=medias, date_for_updates_to_ignore=date_for_updates_to_ignore, discord_id=ctx.author.id
            )
        await ctx.send(f"You will be notified when {media_name} is available to purchase from bestbuy.ca")

    @commands.command(help="List all alerts")
    async def alerts(self, ctx: Context):
        print(f"getting notifications for user {ctx.author.id}")
        message = ""
        person_to_alert = await self.get_user_by_discord_id(ctx.author.id)
        if person_to_alert is not None:
            message += "ID - Media Name\n"
            for alert in await self.get_alerts_by_discord_id(person_to_alert):
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

    @commands.command(help="removes an item from the list of items you will get alerted about")
    async def remove_alert(self, ctx: Context, alert_id: int):
        print(f"removing alert item {alert_id} for {ctx.author.id}")
        await self.remove_alerts(ctx.author.id, alert_id)
        await ctx.send(f"Notification with ID {alert_id} removed")

    @commands.command(help="Removes all your alerts")
    async def remove_all_alerts(self, ctx: Context):
        print(f"removing all alerts for {ctx.author.id}")
        await self.remove_all_current_alerts(ctx.author.id)
        await ctx.send("All your notifications have beem removed")

    @commands.command(help="Clear any information associated with you from the bot")
    async def clear_data(self, ctx: Context):
        print(f"clearing all data for {ctx.author.id}")
        await self.clear_user_data(ctx.author.id)
        await ctx.send("Your data and alerts has been wiped.")

    @commands.command(help="Get the url for the website which shows all current steelbooks")
    async def steelbooks(self, ctx: Context):
        await ctx.send("http://127.0.0.1:8000")

    @commands.command(help="Set channel for alerts to be sent on")
    @commands.check(check_is_owner)
    async def channel(self, ctx: Context):
        guild_obj = await self.get_guild_by_id(guild_id=ctx.guild.id)
        if len(ctx.message.channel_mentions) > 0:
            mentioned_channel = ctx.message.channel_mentions[0]
            if guild_obj is None:
                guild_obj = Guild(
                    guild_id=ctx.guild.id, guild_name=ctx.guild.name, channel_name=mentioned_channel.name,
                    channel_id=mentioned_channel.id
                )
            await self.save_channel_to_alert_on(guild_obj)
        if guild_obj is not None:
            await ctx.send(f"Channel set to {guild_obj.channel_name}")
        else:
            await ctx.send("No Channel set to alerts")

    @commands.command(help="clear channel for alerts to be sent on")
    @commands.check(check_is_owner)
    async def clear_channel(self, ctx: Context):
        guild_obj = await self.get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is not None:
            await self.delete_channel(guild_obj)

    @commands.command(help="Add a role that has to be tagged")
    @commands.check(check_is_owner)
    async def tag_role(self, ctx: Context):
        guild_obj = await self.get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        if len(ctx.message.role_mentions) > 0:
            mentioned_role = ctx.message.role_mentions[0]
            role_to_target_for_guild = await self.get_role_to_target_by_name(role_to_tag_name=mentioned_role.name)
            await self.save_role_to_target(guild_obj, mentioned_role.name, mentioned_role, role_to_target_for_guild)
            await ctx.send(f"Role \"{mentioned_role.name}\" will be tagged")
        else:
            await ctx.send(f"No role was mentioned")

    @commands.command(help="List roles to tag for alerts")
    @commands.check(check_is_owner)
    async def roles_to_tag(self, ctx: Context):
        guild_obj = await self.get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        roles_to_tag = await self.get_roles_to_tag_by_guild_id(guild_obj.guild_id)
        if len(roles_to_tag) > 0:
            message = f"Roles that will be tagged:\n"
            for role_to_tag in roles_to_tag:
                message += f"{role_to_tag.role_to_tag_name}\n"
            await ctx.send(message)
        else:
            await ctx.send(f"No role are set to be tagged")

    @commands.command(help="Stop a role from being tagged")
    @commands.check(check_is_owner)
    async def dont_tag_role(self, ctx: Context):
        guild_obj = await self.get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        if len(ctx.message.role_mentions) > 0:
            mentioned_role = ctx.message.role_mentions[0]
            await self.delete_role_by_name(mentioned_role.name)
            await ctx.send(f"Role \"{mentioned_role.name}\" will no longer be tagged")
        else:
            await ctx.send(f"No role was mentioned")

    @commands.command(help="Stop tagging all roles")
    @commands.check(check_is_owner)
    async def dont_tag_roles(self, ctx: Context):
        guild_obj = await self.get_guild_by_id(guild_id=ctx.guild.id)
        if guild_obj is None:
            await ctx.send("There is no channel set yet for this guild_obj yet. Please call `.channel`")
            return
        await self.delete_role_by_guild(guild_obj.guild_id)
        await ctx.send(f"All tagged roles for this guild have been removed")

    @commands.Cog.listener(name='on_ready')
    async def alert_users_once_an_hour(self):
        while True:
            now = datetime.datetime.now()
            if now.minute == 0:
                print(f"time to alert the users on the hour at {now}")
                number_of_medias, medias, date_for_updates_to_ignore = await self.get_latest_medias(
                    limit_search_to_new_media=True
                )
                if number_of_medias > 0:
                    await self.send_alert_to_guilds(medias)
                    users = await self.get_all_users()
                    print(f"got {len(users)} users to notify")
                    for user in users:
                        await self.alert_users_of_positive_matches(
                            medias, date_for_updates_to_ignore, discord_id=user.discord_id
                        )
            await asyncio.sleep(60)

    @commands.Cog.listener(name="on_command_error")
    async def error(self, ctx: Context, error: CheckFailure):
        if isinstance(error, MissingRequiredArgument) or isinstance(error, CheckFailure):
            await ctx.send(f"{error}")

    @sync_to_async
    def get_latest_medias(self, limit_search_to_new_media: bool = False) -> tuple[int, List[Media], datetime.datetime]:
        date_for_updates_to_ignore = datetime.datetime.now()
        medias = Media.objects.all().filter(
            needs_to_be_processed_by_bot=True) if limit_search_to_new_media else Media.objects.all()
        if limit_search_to_new_media:
            for media in medias:
                media.needs_to_be_processed_by_bot = False
            date_for_updates_to_ignore = datetime.datetime.now()
            Media.objects.bulk_update(medias, ['needs_to_be_processed_by_bot'])
        return len(medias), medias, date_for_updates_to_ignore

    @sync_to_async
    def alert_users_of_positive_matches(self, medias: QuerySet[Media], date_for_updates_to_ignore: datetime.datetime,
                                        discord_id: int = None):

        alerts = Alert.objects.all() \
            if discord_id is None \
            else Alert.objects.all().filter(person_to_alert__discord_id=discord_id)

        for alert in alerts:
            match_media_for_alert = []
            latest_times_alert_was_used_for_specific_medias = \
                LastTimeAlertWasUsedForSpecificMedia.objects.all().filter(
                    alert=alert
                )
            for matching_media in medias.filter(sku__in=self.get_matching_skus(alert.media_search_string)):
                latest_time_alert_was_used_for_specific_media = \
                    latest_times_alert_was_used_for_specific_medias.filter(media=matching_media)
                if latest_time_alert_was_used_for_specific_media is None:
                    # first time that this alert is being used for this item
                    media_was_updated_after_ignore_mapping = True
                else:
                    media_was_updated_after_ignore_mapping = \
                        latest_time_alert_was_used_for_specific_media.date_for_updates_to_ignore < \
                        matching_media.get_latest_quantity().date
                if matching_media.order_can_be_placed() and media_was_updated_after_ignore_mapping:
                    match_media_for_alert.append(matching_media)

            for matching_media in match_media_for_alert:
                BestBuyBot.send_alerts(alert, matching_media, date_for_updates_to_ignore)

    @staticmethod
    def send_alerts(alert: Alert, media: Media, date_for_updates_to_ignore: datetime.datetime):
        media_that_alert_has_to_ignore = LastTimeAlertWasUsedForSpecificMedia.objects.all().get_or_create(
            alert=alert,
            media=media
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
            alert.person_to_alert.send_sms(media.name)

    @sync_to_async
    def send_alert_to_guilds(self, medias: List[Media]):
        guilds = Guild.objects.all()
        for guild in guilds:
            channel_name = guild.guild_name
            channel_id = guild.channel_id
            matching_guild = [guild for guild in self.bot.guilds if guild.id == 478433247643303936]
            roles = guild.roletotargetforguild_set.all()
            if len(matching_guild) > 0:
                matching_guild = matching_guild[0]
                channel_matching_by_id = False
                channel_matching_by_name = None
                for channel in matching_guild.text_channels:
                    if channel.id == channel_id:
                        channel_matching_by_id = True
                    if channel.name == channel_name:
                        channel_matching_by_name = channel
                    if channel_matching_by_id:
                        break
                if channel_matching_by_id:
                    for media in medias:
                        guild.send_alert(roles, channel_id, media)
                elif channel_matching_by_name is not None:
                    for media in medias:
                        guild.send_alert(roles, channel_matching_by_name.id, media)

    @sync_to_async
    def save_to_alerts(self, discord_id: int, media_name: str):
        print(f"saving search for {media_name} for discord_id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            people_to_alert = User(discord_id=discord_id)
            people_to_alert.save()
        alert_obj = Alert(person_to_alert=people_to_alert, media_search_string=media_name)
        alert_obj.save()

    @sync_to_async
    def get_user_by_discord_id(self, discord_id: int) -> User:
        return User.objects.all().filter(discord_id=discord_id).first()

    @sync_to_async
    def delete_channel(self, guild_obj: Guild):
        guild_obj.delete()

    @sync_to_async
    def get_guild_by_id(self, guild_id: int) -> Guild:
        return Guild.objects.all().filter(guild_id=guild_id).first()

    @sync_to_async
    def get_roles_to_tag_by_guild_id(self, guild_id: int) -> List[Role]:
        return list(RoleToTargetForGuild.objects.all().filter(guild__guild_id=guild_id))

    @sync_to_async
    def get_role_to_target_by_name(self, role_to_tag_name: int) -> RoleToTargetForGuild:
        return RoleToTargetForGuild.objects.all().filter(role_to_tag_name=role_to_tag_name).first()

    @sync_to_async
    def delete_role_by_name(self, role_to_tag_name: int):
        role_to_tag = RoleToTargetForGuild.objects.all().filter(role_to_tag_name=role_to_tag_name).first()
        if role_to_tag is not None:
            role_to_tag.delete()

    @sync_to_async
    def delete_role_by_guild(self, guild_id: int = None):
        RoleToTargetForGuild.objects.all().filter(guild_id=guild_id).delete()

    @sync_to_async
    def save_channel_to_alert_on(self, guild_obj: Guild):
        guild_obj.save()

    @sync_to_async
    def save_role_to_target(
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

    @sync_to_async
    def get_all_users(self) -> list[User]:
        return list(User.objects.all())

    @sync_to_async
    def save_email_address(self, discord_id: int, email: str) -> Optional[str]:
        print(f"saving email for discord id {discord_id}")
        if not re.match(r"^\w+@(gmail|hotmail|protonmail|sfu|outlook|icloud|me)\.(com|ca)+$", email):
            return "Invalid email detected"
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            people_to_alert = User(discord_id=discord_id)
        people_to_alert.email = email
        people_to_alert.save()
        return None

    @sync_to_async
    def clear_email_address(self, discord_id: int):
        print(f"deleting email for discord id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            return
        people_to_alert.email = None
        people_to_alert.save()

    @sync_to_async
    def save_phone_number(self, discord_id: int, phone_number: str):
        print(f"saving phone_number {phone_number} for discord id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            people_to_alert = User(discord_id=discord_id)
        people_to_alert.phone_number = phone_number
        people_to_alert.save()

    @sync_to_async
    def clear_phone_number(self, discord_id: int):
        print(f"deleting sms for discord id {discord_id}")
        people_to_alert = User.objects.all().filter(discord_id=discord_id).first()
        if people_to_alert is None:
            return
        people_to_alert.phone_number = None
        people_to_alert.save()

    @sync_to_async
    def get_alerts_by_discord_id(self, person_to_alert: User) -> List[Alert]:
        return list(person_to_alert.alert_set.all())

    @sync_to_async
    def remove_alerts(self, discord_id: int, alert_id: int):
        media_alert = Alert.objects.all().filter(
            person_to_alert__discord_id=discord_id, id=alert_id
        ).first()
        if media_alert is not None:
            media_alert.delete()

    @sync_to_async
    def remove_all_current_alerts(self, discord_id: int):
        Alert.objects.all().filter(person_to_alert__discord_id=discord_id).delete()

    @sync_to_async
    def clear_user_data(self, discord_id: int):
        User.objects.all().filter(discord_id=discord_id).delete()

    def get_matching_skus(self, search_string: str) -> list[str]:
        response = requests.get(
            f"https://www.bestbuy.ca/api/v2/json/search?categoryid=&currentRegion=ON&include=facets,"
            f"redirects&lang=en-CA&page=1&pageSize=24&path=&query={search_string}&exp=&sortBy=relevance"
            f"&sortDir=desc",
            headers=self.headers
        )
        return [product['sku'] for product in response.json()['products']]


# put on https://steelbooksatbestbuy.ca


bot.add_cog(BestBuyBot(bot))
bot.run(os.environ["TOKEN"])
