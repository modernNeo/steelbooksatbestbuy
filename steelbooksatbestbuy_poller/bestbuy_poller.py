import datetime
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from time import sleep
from typing import List

import django
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from twilio.rest import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from steelbooksatbestbuy.models import Media, QuantityUpdate, User


class BestBuyAPI:

    def __init__(self):
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

    def get_latest_medias(self, limit_search_to_new_media: bool = False) -> tuple[int, List[Media], datetime.datetime]:
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

    def poll_bestbuy(self):
        timezone_offset = -8.0
        tzinfo = datetime.timezone(datetime.timedelta(hours=timezone_offset))
        now = datetime.datetime.now(tzinfo)
        print(f"polling has started at {now}")
        base_url = f"https://www.bestbuy.ca/api/v2/json/search?pageSize=100&query=steelbook"
        print(f"trying to get data from url {base_url}")
        response = requests.get(base_url, headers=self.headers)
        print(f"data received from url {base_url}")
        total_pages = response.json()['totalPages']
        total_products = []
        for movies_listing_page in range(1, total_pages + 1):
            products_in_current_page = []
            url = f"{base_url}&page={movies_listing_page}"
            retry = 0
            while len(products_in_current_page) == 0 and retry < 5:
                print(f"trying to get data from url {url}, attempt [{retry}/{5}]")
                products_in_current_page = requests.get(url, headers=self.headers).json()['products']
                retry += 1
                if retry == 5:
                    print(f"endpoint {url} not returning any products..")
            if len(products_in_current_page) > 0:
                total_products.extend(products_in_current_page)
                print(f"{len(products_in_current_page)} products received from url {url}")
        total_number_of_products = response.json()['total']
        medias = Media.objects.all()
        index_so_far = 0
        faulty_products = []
        for product in total_products:
            sku = product['sku']
            product_info_base_url = (
                f"https://www.bestbuy.ca/ecomm-api/availability/products?accept=application%2Fvnd.bestbuy."
                f"standardproduct.v1%2Bjson&accept-language=en-CA&locations=&postalCode=&skus={sku}"
            )
            retry = 0
            successful = False
            error = None
            while not successful and retry < 5:
                try:
                    print(f"trying to get {product_info_base_url}")
                    resp = requests.get(product_info_base_url, headers=self.headers)
                    product_info = json.loads(resp.text.encode().decode('utf-8-sig'))
                    print("url received")
                    media = medias.filter(name=product['name']).first()
                    current_quantities_remaining = product_info['availabilities'][0]['shipping'][
                        'quantityRemaining']
                    regular_price = product['regularPrice']
                    sales_price = product['salePrice']
                    purchaseable_via_pickup = product_info['availabilities'][0]['pickup']['purchasable']
                    pickup_status = product_info['availabilities'][0]['pickup']['status']
                    purchaseable_via_shipping = product_info['availabilities'][0]['shipping']['purchasable']
                    online_order_status = product_info['availabilities'][0]['shipping']['status']
                    if media is None:
                        media = medias.filter(sku=product['sku']).first()
                        if media is not None:
                            print(
                                f"mis-match between name from endpoint [{product['name']}] and name in DB [{media.name}]")
                        else:
                            print(f"new item detected [{product['name']}] from bestbuy's website...")
                    orderable_property_changed = True
                    if media is not None:
                        latest_time_quantity_was_changed = media.get_latest_quantity()
                        orderable_property_changed = latest_time_quantity_was_changed.orderable_property_changed(
                            current_quantities_remaining, regular_price, sales_price, purchaseable_via_pickup,
                            purchaseable_via_shipping, pickup_status, online_order_status
                        )
                        if orderable_property_changed:
                            media.product_url = f"https://www.bestbuy.ca{product['productUrl']}"
                            media.set_orderable_status(pickup_status, online_order_status)
                            media.save()
                            QuantityUpdate(
                                media=media, date=now,
                                quantity=current_quantities_remaining,
                                regular_price=regular_price,
                                sales_price=sales_price,
                                sales_channel_exclusivity=
                                product_info['availabilities'][0]['saleChannelExclusivity'],
                                purchaseable_via_pickup=purchaseable_via_pickup,
                                status_for_pickup=pickup_status,
                                purchaseable_via_shipping=purchaseable_via_shipping,
                                status_for_shipping=online_order_status
                            ).save()
                        else:
                            media.set_flag_to_be_ignored_by_bot()
                        index_so_far += 1
                        print(
                            f"{now}-info for media that already existed in media:"
                            "\n\tquantity, price, order, or "
                            f"status{' ' if orderable_property_changed else 'did not '}"
                            f"change{'d ' if orderable_property_changed else ' '}for {media.name} [{index_so_far}"
                            f"/{total_number_of_products}] in database"
                            f"\n\tmedia is set to {'' if media.needs_to_be_processed_by_bot else 'not '}be "
                            f"processed by the bot"
                            f"\n\tpickup_status=[{pickup_status}] && online_order_status=[{online_order_status}]"
                        )
                    else:
                        media = Media(
                            name=product['name'],
                            product_url=f"https://www.bestbuy.ca{product['productUrl']}",
                            image=product['thumbnailImage'],
                            sku=product['sku']
                        )
                        media.set_orderable_status(pickup_status, online_order_status)
                        media.save()
                        QuantityUpdate(
                            media=media, date=now,
                            quantity=current_quantities_remaining,
                            regular_price=regular_price, sales_price=sales_price,
                            sales_channel_exclusivity=
                            product_info['availabilities'][0]['saleChannelExclusivity'],
                            purchaseable_via_pickup=purchaseable_via_pickup,
                            status_for_pickup=pickup_status,
                            purchaseable_via_shipping=purchaseable_via_shipping,
                            status_for_shipping=online_order_status
                        ).save()
                        print(
                            f"{now}-info for new media:"
                            "\n\tquantity, price, order, or "
                            f"status{' ' if orderable_property_changed else 'did not '}"
                            f"change{'d ' if orderable_property_changed else ' '}for {media.name} [{index_so_far}"
                            f"/{total_number_of_products}] in database"
                            f"\n\tmedia is set to {'' if media.needs_to_be_processed_by_bot else 'not '}be "
                            f"processed by the bot"
                            f"\n\tpickup_status=[{pickup_status}] && online_order_status=[{online_order_status}]"
                        )
                        index_so_far += 1
                    sleep(3)
                    successful = True
                except Exception as e:
                    print(
                        f"attempt [{retry}/5] tried for product {product['name']}, error \"{e}\" "
                        f"encountered"
                    )
                    retry += 1
                    successful = False
                    error = e
                    sleep(5)
            if retry == 5 and not successful:
                faulty_products.append({
                    "product": product['name'],
                    "SKU": product['sku'],
                    "url": product_info_base_url,
                    "error": error
                })
        print(f"Was able to save [{index_so_far}/{total_number_of_products}] medias to database")
        print(f"time to alert the users and guilds on the hour at {now}")
        number_of_medias, medias, date_for_updates_to_ignore = self.get_latest_medias(
            limit_search_to_new_media=True
        )
        print(f"got {number_of_medias} medias that the guilds and users have to be alerted about")
        if number_of_medias > 0:
            body = ""
            for media in medias:
                quantity_info = media.get_latest_quantity()
                body += f"""{media.name}\n
Price - Regular : {quantity_info.regular_price} | Sales : 
{quantity_info.sales_price}\nQuantity: {quantity_info.quantity} \n
[Link]({media.product_url})\n\n"""
            send_email("SteelbooksAtBestBuy Alert", body)
        if len(faulty_products) > 0:
            alert_me_of_faulty_product_calls(faulty_products)


def send_email(subject: str = None, body: str = None):
    from_person_name = 'BestBuy-Steelbooks'
    from_person_email = 'bestbuy.steelbooks@gmail.com'
    password = f"{os.environ['BESTBUY_STEELBOOKS_PASSWORD']}"
    to_person_email = f"{os.environ['JACE_EMAIL']}"

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
    print(f"email sent to {to_person_email}")
    client = Client(f"{os.environ['TWILIO_ACCOUNT_SID']}", f"{os.environ['TWILIO_AUTH_TOKEN']}")

    # change the "from_" number to your Twilio number and the "to" number
    # to the phone number you signed up for Twilio with, or upgrade your
    # account to send SMS to any phone number
    client.messages.create(to=f"{os.environ['JACE_NUMBER']}",
                           from_=f"{os.environ['TWILIO_VIRTUAL_NUMBER']}",
                           body="check your email new steelbooks")


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

if __name__ == '__main__':
    best_buy_api = BestBuyAPI()

    scheduler = BlockingScheduler()
    best_buy_api.poll_bestbuy()
    scheduler.add_job(func=best_buy_api.poll_bestbuy, hours=1, trigger='interval')
    scheduler.start()
