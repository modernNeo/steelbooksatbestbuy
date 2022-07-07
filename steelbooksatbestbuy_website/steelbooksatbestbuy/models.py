import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from django.db import models
from twilio.rest import Client

PICKUP_STATUS_NOT_ORDER_ABLE = ["OutOfStock", "NotAvailable", "OnlineOnly"]
SHIPPING_STATUS_NOT_ORDER_ABLE = ["SoldOutOnline", "Unknown"]


class Media(models.Model):
    name = models.CharField(
        max_length=300
    )
    product_url = models.CharField(
        max_length=300
    )
    image = models.CharField(
        max_length=300
    )

    archived = models.BooleanField(
        default=False
    )

    sku = models.CharField(
        max_length=300,
        unique=True
    )

    needs_to_be_processed_by_bot = models.BooleanField(

    )

    @property
    def order_able(self):
        if self.get_latest_quantity() is None:
            return False
        return (
            (self.get_latest_quantity().status_for_pickup not in PICKUP_STATUS_NOT_ORDER_ABLE) or
            (self.get_latest_quantity().status_for_shipping not in SHIPPING_STATUS_NOT_ORDER_ABLE)
        )

    def set_flag_to_be_processed_by_bot(self):
        self.needs_to_be_processed_by_bot = True

    def set_flag_to_be_ignored_by_bot(self):
        self.needs_to_be_processed_by_bot = False

    def set_orderable_status(self, new_pickup_status: str, new_online_order_status: str):
        latest_quantity = self.get_latest_quantity()
        if latest_quantity is None:
            print(f"new_pickup_status=[{new_pickup_status}] && new_online_order_status=[{new_online_order_status}]")
            order_able_again = (
                (new_pickup_status not in PICKUP_STATUS_NOT_ORDER_ABLE) or
                (new_online_order_status not in SHIPPING_STATUS_NOT_ORDER_ABLE)
            )
        else:
            print(
                f"latest_quantity.status_for_pickup=[{latest_quantity.status_for_pickup}] && "
                f"latest_quantity.status_for_shipping=[{latest_quantity.status_for_shipping}]"
            )
            print(f"new_pickup_status=[{new_pickup_status}] && new_online_order_status=[{new_online_order_status}]")
            order_able_again = (
                (
                    latest_quantity.status_for_pickup in PICKUP_STATUS_NOT_ORDER_ABLE and
                    latest_quantity.status_for_pickup != new_pickup_status and
                    new_pickup_status not in PICKUP_STATUS_NOT_ORDER_ABLE
                ) or
                (
                    latest_quantity.status_for_shipping in SHIPPING_STATUS_NOT_ORDER_ABLE and
                    latest_quantity.status_for_shipping != new_online_order_status and
                    new_online_order_status not in SHIPPING_STATUS_NOT_ORDER_ABLE
                )
            )
        print(f"order_able_again=[{order_able_again}]")
        if order_able_again:
            self.set_flag_to_be_processed_by_bot()
        else:
            self.set_flag_to_be_ignored_by_bot()

    def get_latest_quantity(self):
        return self.quantityupdate_set.order_by('-date').first()

    def __str__(self):
        return f"{self.sku} - {self.name}"


class QuantityUpdate(models.Model):
    media = models.ForeignKey(
        Media,
        on_delete=models.CASCADE
    )

    date = models.DateTimeField(

    )
    quantity = models.IntegerField(

    )
    regular_price = models.FloatField(

    )
    sales_price = models.FloatField(

    )
    sales_channel_exclusivity = models.CharField(
        max_length=300
    )
    purchaseable_via_pickup = models.BooleanField(
    )
    status_for_pickup = models.CharField(
        max_length=300
    )
    purchaseable_via_shipping = models.BooleanField(
    )
    status_for_shipping = models.CharField(
        max_length=300
    )

    def order_can_be_placed(self):
        return self.purchaseable_via_pickup or self.purchaseable_via_shipping

    def orderable_property_changed(
        self, new_quantity: int, new_regular_price: int, new_sales_price: int, new_purchaseable_via_pickup: bool,
        new_purchaseable_via_shipping: bool, new_pickup_status: str, new_online_order_status: str
    ):
        return (
            self.quantity < new_quantity  # only want this updated when there is new stock. not when people buy
            or self.regular_price != new_regular_price or
            self.sales_price != new_sales_price or self.purchaseable_via_pickup != new_purchaseable_via_pickup or
            self.purchaseable_via_shipping != new_purchaseable_via_shipping or
            self.status_for_pickup != new_pickup_status or
            self.status_for_shipping != new_online_order_status
        )


class Guild(models.Model):
    guild_id = models.IntegerField(
        unique=True
    )
    guild_name = models.CharField(
        max_length=300
    )

    channel_id = models.IntegerField(
        unique=True
    )
    channel_name = models.CharField(
        max_length=300
    )

    @staticmethod
    def send_alert(roles: list[any], channel_id, media):
        quantity_info = media.get_latest_quantity()
        content = ""
        for role in roles:
            content += f"<@&{role.role_to_tag_id}> "
        requests.post(
            f"https://discord.com/api/channels/{channel_id}/messages",
            data=json.dumps(
                {
                    "embeds": [{
                        "title": f"{media.name} now available at Bestbuy.ca",
                        "image": {
                            "url": media.image
                        },
                        "description": (
                            f"Price - Regular : {quantity_info.regular_price} | Sales : "
                            f"{quantity_info.sales_price}\nQuantity: {quantity_info.quantity} \n"
                            f"[Link]({media.product_url})\n\n"
                        )
                    }],
                    "content": content
                }),
            headers={
                "Authorization": f"Bot {os.environ['TOKEN']}",
                "Content-Type": "application/json"
            }
        )

    def __str__(self):
        return f"Guild: {self.guild_name}"


class RoleToTargetForGuild(models.Model):
    guild = models.ForeignKey(
        Guild,
        on_delete=models.CASCADE
    )
    role_to_tag_name = models.CharField(
        max_length=500
    )
    role_to_tag_id = models.IntegerField(
    )

    def save(self, *args, **kwargs):
        duplicate = RoleToTargetForGuild.objects.all()
        if self.id is not None:
            duplicate = duplicate.filter(
                guild_id=self.guild_id,
                role_to_tag_name=self.role_to_tag_name,
                role_to_tag_id=self.role_to_tag_id,
            ).exclude(id=self.id).first()
        else:
            duplicate = duplicate.filter(
                guild_id=self.guild_id,
                role_to_tag_name=self.role_to_tag_name,
                role_to_tag_id=self.role_to_tag_id,
            ).first()
        if duplicate is None:
            super(RoleToTargetForGuild, self).save(*args, **kwargs)
            return None
        else:
            return f"role {self.role_to_tag_name} already saved"


class User(models.Model):
    discord_id = models.IntegerField(

    )
    email = models.CharField(
        max_length=300,
        default=None,
        null=True,
        blank=True
    )
    phone_number = models.IntegerField(
        default=None,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Person [{self.id}] with Discord Id {self.discord_id}"

    def send_discord_dm(self, media: Media, media_search_string: str):
        response = requests.post(
            "https://discord.com/api/users/@me/channels",
            data=json.dumps({
                "recipient_id": self.discord_id
            }),
            headers={
                "Authorization": f"Bot {os.environ['TOKEN']}",
                "Content-Type": "application/json"
            }
        )
        if response.status_code:
            quantity_info = media.get_latest_quantity()
            requests.post(
                f"https://discord.com/api/channels/{response.json()['id']}/messages",
                data=json.dumps(
                    {
                        "tts": False,
                        "embeds": [{
                            "title": f"{media.name} now available at Bestbuy.ca",
                            "image": {
                                "url": media.image
                            },
                            "description": (
                                f"Price - Regular : {quantity_info.regular_price} | Sales : "
                                f"{quantity_info.sales_price}\nQuantity: {quantity_info.quantity} \n"
                                f"[Link]({media.product_url})\n\n"
                                f"Notification for: \"{media_search_string}\"\n\n"
                            )
                        }]
                    }),
                headers={
                    "Authorization": f"Bot {os.environ['TOKEN']}",
                    "Content-Type": "application/json"
                }
            )
            requests.post(
                f"https://discord.com/api/channels/{response.json()['id']}/messages",
                data=json.dumps(
                    {
                        "tts": False,
                        "content": (
                            f"To stop being notified about this item, please use the `.remove_alert` command in the "
                            f"the discord guild"
                        )
                    }),
                headers={
                    "Authorization": f"Bot {os.environ['TOKEN']}",
                    "Content-Type": "application/json"
                }
            )
            print(
                f"Discord notification sent to user {self.discord_id} for media {media} "
                f"for search string {media_search_string}"
            )
        else:
            print(
                f"Unable to send discord notification to user {self.discord_id} for media {media} "
                f"for search string {media_search_string} due to error {response.json()['message']}"
            )

    def send_email(self, movie_name: str = None, movie_link: str = None):
        from_person_name = 'BestBuy-Steelbooks'
        from_person_email = 'bestbuy.steelbooks@gmail.com'
        password = f"{os.environ['BESTBUY_STEELBOOKS_PASSWORD']}"
        to_person_email = "TBD" if self.email is None else self.email
        subject = f'{movie_name} is now in stock at bestbuy.ca'
        body = f"<a href={movie_link}>{movie_name}</a>"

        print("Setting up MIMEMultipart object")
        msg = MIMEMultipart()
        msg['From'] = from_person_name + " <" + from_person_email + ">"
        msg['To'] = " <" + to_person_email + ">"
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        print("Connecting to smtp.gmail.com:587")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.connect("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        print("Logging into your gmail")
        server.login(from_person_email, password)
        print("Sending email...")
        server.send_message(from_addr=from_person_email, to_addrs=to_person_email, msg=msg)
        server.close()
        print(f"email sent to {self.discord_id} for movie {movie_name}")

    def send_sms(self, movie_name: str = None, movie_link: str = None):
        # https://www.fullstackpython.com/blog/send-sms-text-messages-python.html
        body = f"{movie_name} is now available: {movie_link}"
        # the following line needs your Twilio Account SID and Auth Token
        client = Client(f"{os.environ['TWILIO_ACCOUNT_SID']}", f"{os.environ['TWILIO_AUTH_TOKEN']}")

        # change the "from_" number to your Twilio number and the "to" number
        # to the phone number you signed up for Twilio with, or upgrade your
        # account to send SMS to any phone number
        client.messages.create(to=f"{self.phone_number}",
                               from_=f"{os.environ['TWILIO_VIRTUAL_NUMBER']}",
                               body=body)
        print(f"text sent to {self.discord_id} for movie {movie_name}")

    @staticmethod
    def alert_me_of_faulty_product_calls(faulty_products):
        from_person_name = 'BestBuy-Steelbooks'
        from_person_email = 'bestbuy.steelbooks@gmail.com'
        password = f"{os.environ['BESTBUY_STEELBOOKS_PASSWORD']}"
        to_person_email = f"{os.environ['JACE_EMAIL']}"
        body = ""

        for faulty_product in faulty_products:
            body += f"Product: {faulty_product['product']} <br>" \
                    f"SKU: {faulty_product['SKU']} <br>" \
                    f"URL: {faulty_product['url']} <br>" \
                    f"error: {faulty_product['error']}<br><br><br>"

        print("Setting up MIMEMultipart object")
        msg = MIMEMultipart()
        msg['From'] = from_person_name + " <" + from_person_email + ">"
        msg['To'] = " <" + to_person_email + ">"
        msg['Subject'] = "fault API Calls"
        msg.attach(MIMEText(body, 'html'))

        print("Connecting to smtp.gmail.com:587")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.connect("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        print("Logging into your gmail")
        server.login(from_person_email, password)
        print("Sending email...")
        server.send_message(from_addr=from_person_email, to_addrs=to_person_email, msg=msg)
        server.close()

        client = Client(f"{os.environ['TWILIO_ACCOUNT_SID']}", f"{os.environ['TWILIO_AUTH_TOKEN']}")

        # change the "from_" number to your Twilio number and the "to" number
        # to the phone number you signed up for Twilio with, or upgrade your
        # account to send SMS to any phone number
        client.messages.create(to=f"{os.environ['JACE_NUMBER']}",
                               from_=f"{os.environ['TWILIO_VIRTUAL_NUMBER']}",
                               body="check your email for faulty API calls")


class Alert(models.Model):
    person_to_alert = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    media_search_string = models.CharField(
        max_length=500
    )

    def save(self, *args, **kwargs):
        duplicate = Alert.objects.all()
        if self.id is not None:
            duplicate = duplicate.filter(
                person_to_alert=self.person_to_alert_id,
                media_search_string=self.media_search_string,
            ).exclude(id=self.id).first()
        else:
            duplicate = duplicate.filter(
                person_to_alert=self.person_to_alert_id,
                media_search_string=self.media_search_string
            ).first()
        if duplicate is None:
            super(Alert, self).save(*args, **kwargs)
            return None
        else:
            return f"{self.media_search_string} is already on your list of alerts"

    def __str__(self):
        return f"[(Alert) {self.person_to_alert} set alert for \"{self.media_search_string}\"]"


class LastTimeAlertWasUsedForSpecificMedia(models.Model):
    media = models.ForeignKey(
        Media,
        on_delete=models.CASCADE
    )
    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE
    )
    date_for_updates_to_ignore = models.DateTimeField(

    )

    def __str__(self):
        return (
            f"[(LastTimeAlertWasUsedForSpecificMedia) "
            f"Alert {self.alert} for media {self.media} "
            f"was last updated on {self.date_for_updates_to_ignore}]"
        )
