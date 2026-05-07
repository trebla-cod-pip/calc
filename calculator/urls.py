from django.urls import path
from . import views

app_name = "calculator"

urlpatterns = [
    # Калькулятор прибыли
    path("", views.index, name="index"),
    path("calculate/", views.calculate, name="calculate"),

    # Настройки приложения
    path("settings/save/", views.save_settings, name="settings_save"),

    # Тарифы банков
    path("tariffs/", views.tariffs, name="tariffs"),
    path("tariffs/<int:pk>/set-default/", views.tariff_toggle_default, name="tariff_set_default"),

    # Потребности
    path("requirements/", views.requirements_list, name="requirements"),
    path("requirements/<int:pk>/delete/", views.requirement_delete, name="requirement_delete"),

    # КП поставщиков
    path("offers/", views.offers_list, name="offers_list"),
    path("offers/all/", views.all_offers_partial, name="all_offers_partial"),
    path("offers/search/", views.search_requirements, name="search_requirements"),
    path("offers/<int:pk>/edit/", views.offer_edit, name="offer_edit"),
    path("offers/<int:pk>/delete/", views.supplier_offer_delete, name="supplier_offer_delete"),

    # Поставки
    path("deliveries/", views.delivery_list, name="delivery_list"),
    path("deliveries/create/", views.delivery_create, name="delivery_create"),
    path("deliveries/<int:pk>/", views.delivery_detail, name="delivery_detail"),
    path("deliveries/<int:pk>/delete/", views.delivery_delete, name="delivery_delete"),
    path("deliveries/items/<int:item_pk>/set-offer/", views.delivery_set_offer, name="delivery_set_offer"),
]
