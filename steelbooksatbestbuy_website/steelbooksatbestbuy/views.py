from django.shortcuts import render
from django.views.generic.base import View

from steelbooksatbestbuy.models import Media

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
