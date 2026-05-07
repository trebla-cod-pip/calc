"""
Административная панель для управления тарифами и настройками налогов.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import BankTariff, TaxSettings


@admin.register(BankTariff)
class BankTariffAdmin(admin.ModelAdmin):
    list_display = ["__str__", "maintenance_fee", "outgoing_other_bank_fee", "is_default", "is_active", "updated_at"]
    list_filter = ["bank", "is_active", "is_default"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        ("Основное", {
            "fields": ["bank", "name", "is_active", "is_default"],
        }),
        ("Обслуживание счёта", {
            "fields": ["maintenance_fee", "maintenance_free_condition"],
        }),
        ("Исходящие платежи", {
            "fields": ["outgoing_same_bank_fee", "outgoing_other_bank_fee"],
        }),
        ("Вывод на личную карту", {
            "fields": ["withdrawal_config"],
            "description": (
                "JSON с настройками прогрессивной шкалы. Пример: "
                '{"free_limit": 150000, "fixed_fee_per_operation": 99, '
                '"tiers": [{"up_to": 400000, "rate": 1.5}, {"up_to": 1000000, "rate": 5.0}, {"up_to": null, "rate": 15.0}]}'
            ),
        }),
        ("Служебное", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def save_model(self, request, obj, form, change):
        # Сбрасываем флаг default у остальных тарифов при установке нового default
        if obj.is_default:
            BankTariff.objects.exclude(pk=obj.pk).filter(is_default=True).update(is_default=False)
        super().save_model(request, obj, form, change)


@admin.register(TaxSettings)
class TaxSettingsAdmin(admin.ModelAdmin):
    list_display = ["year", "fixed_insurance_annual", "additional_insurance_threshold", "additional_insurance_rate"]
    ordering = ["-year"]
