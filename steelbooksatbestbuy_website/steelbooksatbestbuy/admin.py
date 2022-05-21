from django.contrib import admin

# Register your models here.
from steelbooksatbestbuy.models import User, Alert, LastTimeAlertWasUsedForSpecificMedia, Media, \
    QuantityUpdate, Guild, RoleToTargetForGuild


class UserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'discord_id',
        'email'
    )


admin.site.register(User, UserAdmin)


class AlertAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'person_to_alert',
        'media_search_string'
    )


admin.site.register(Alert, AlertAdmin)


class LastTimeAlertWasUsedForSpecificMediaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'media',
        'alert'
    )


admin.site.register(LastTimeAlertWasUsedForSpecificMedia, LastTimeAlertWasUsedForSpecificMediaAdmin)


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


class GuildAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'guild_id',
        'guild_name',
        'channel_id',
        'channel_name',
    )


admin.site.register(Guild, GuildAdmin)

class RoleToTargetForGuildAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'guild',
        'role_to_tag_name',
        'role_to_tag_id'
    )


admin.site.register(RoleToTargetForGuild, RoleToTargetForGuildAdmin)