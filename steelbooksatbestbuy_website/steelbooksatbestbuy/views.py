import json
import re

import requests
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic.base import View

from steelbooksatbestbuy.models import Media, User, Alert

media_filter = {
    "price": "quantityupdate__regular_price",
    "quantity": "quantityupdate__quantity"
}


class Index(View):

    @staticmethod
    def context_creator(request):
        medias = Media.objects.all()
        if request.GET.get("all", None) is None:
            skus_to_show = [
                media.sku
                for media in medias if media.get_latest_quantity().order_can_be_placed()
            ]
            medias = medias.filter(sku__in=skus_to_show)
        if request.GET.get("sort", None) is not None:

            get_dict = request.GET
            if get_dict.get("sort") in media_filter and get_dict.get("order", None) is not None:
                medias = list(
                    {
                        media.sku: media
                        for media in medias.order_by(
                        ('-' if request.GET.get("order") == "desc" else "") + media_filter[request.GET.get("sort")]
                    )
                    }.values()
                )
        else:
            medias = list({
                              media.sku: media
                              for media in medias.order_by('-quantityupdate__quantity')
                          }.values())
        return medias

    def get(self, request):
        return render(request, 'steelbooksatbestbuy/index.html', context={'medias': Index.context_creator(request)})

    def post(self, request):
        context = {'medias': Index.context_creator(request)}
        movies = request.POST.get("movies", None)
        if movies is None:
            context['error'] = "Invalid Movie specified"
            return render(request, 'steelbooksatbestbuy/index.html', context=context)
        else:
            movies = movies.split("\r\n")
        email = request.POST.get("email", None)
        if email is not None and (
            len(email) > 0 and not re.match(r"^\w+@(gmail|hotmail|protonmail|sfu|outlook|icloud|me)\.(com|ca)+$",
                                            email)):
            context['error'] = "Invalid Email Specified"
            return render(request, 'steelbooksatbestbuy/index.html', context=context)
        else:
            email = None if email is None or len(email) == 0 else email
        phone_number = request.POST.get("phone_number", None)
        if phone_number is not None and not (len(phone_number) == 0 or len(phone_number) == 10):
            context['error'] = "Invalid Phone Number Specified"
            return render(request, 'steelbooksatbestbuy/index.html', context=context)
        else:
            phone_number = None if phone_number is None or len(phone_number) == 0 else phone_number
        people_to_alert = User.objects.all().filter(email=email).first()
        if people_to_alert is None:
            people_to_alert = User(email=email, phone_number=phone_number)
            people_to_alert.save()
        for movie in movies:
            Alert(person_to_alert=people_to_alert,
                  media_search_string=movie).save()
        return HttpResponseRedirect("")
