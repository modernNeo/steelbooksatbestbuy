from django.contrib import admin

# Register your models here.
from steelbooksatbestbuy.models import Media, QuantityUpdate


class MediaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'archived',
        'sku',
        'needs_to_be_processed_by_bot'
    )


admin.site.register(Media, MediaAdmin)


class QuantityUpdateAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'media',
        'date',
        'quantity',
        'regular_price',
        'sales_price',
        'purchaseable_via_pickup',
        'status_for_pickup',
        'purchaseable_via_shipping',
        'status_for_shipping'
    )


admin.site.register(QuantityUpdate, QuantityUpdateAdmin)