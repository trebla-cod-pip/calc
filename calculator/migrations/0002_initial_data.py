# Начальные данные: тарифы Т-Банка 2026 и настройки налогов ИП
from django.db import migrations


TBANK_SIMPLE_WITHDRAWAL = {
    "free_limit": 150_000,
    "fixed_fee_per_operation": 99,
    "tiers": [
        {"up_to": 400_000,   "rate": 1.5},
        {"up_to": 1_000_000, "rate": 5.0},
        {"up_to": None,      "rate": 15.0},
    ],
}

TBANK_ADVANCED_WITHDRAWAL = {
    "free_limit": 400_000,
    "fixed_fee_per_operation": 79,
    "tiers": [
        {"up_to": 1_000_000, "rate": 3.0},
        {"up_to": None,      "rate": 10.0},
    ],
}

TBANK_PRO_WITHDRAWAL = {
    "free_limit": 1_000_000,
    "fixed_fee_per_operation": 0,
    "tiers": [
        {"up_to": None, "rate": 5.0},
    ],
}


def create_initial_data(apps, schema_editor):
    BankTariff = apps.get_model("calculator", "BankTariff")
    TaxSettings = apps.get_model("calculator", "TaxSettings")

    # ── Т-Банк: «Простой» ──
    BankTariff.objects.create(
        bank="tbank",
        name="Простой",
        is_active=True,
        is_default=True,
        maintenance_fee="490.00",
        maintenance_free_condition=(
            "Нет операций ИЛИ покупки по бизнес-карте ≥ 150 000 ₽/мес "
            "ИЛИ покупки ≥ 400 000 ₽/мес"
        ),
        outgoing_same_bank_fee="0.00",
        outgoing_other_bank_fee="49.00",
        withdrawal_config=TBANK_SIMPLE_WITHDRAWAL,
    )

    # ── Т-Банк: «Продвинутый» ──
    BankTariff.objects.create(
        bank="tbank",
        name="Продвинутый",
        is_active=True,
        is_default=False,
        maintenance_fee="1990.00",
        maintenance_free_condition=(
            "Покупки по бизнес-карте ≥ 400 000 ₽/мес"
        ),
        outgoing_same_bank_fee="0.00",
        outgoing_other_bank_fee="0.00",   # в Продвинутом межбанк бесплатный
        withdrawal_config=TBANK_ADVANCED_WITHDRAWAL,
    )

    # ── Т-Банк: «Профессиональный» ──
    BankTariff.objects.create(
        bank="tbank",
        name="Профессиональный",
        is_active=True,
        is_default=False,
        maintenance_fee="4990.00",
        maintenance_free_condition="",
        outgoing_same_bank_fee="0.00",
        outgoing_other_bank_fee="0.00",
        withdrawal_config=TBANK_PRO_WITHDRAWAL,
    )

    # ── Настройки налогов и взносов 2026 ──
    TaxSettings.objects.create(
        year=2026,
        fixed_insurance_annual="49500.00",
        additional_insurance_threshold="300000.00",
        additional_insurance_rate="1.00",
    )


def remove_initial_data(apps, schema_editor):
    BankTariff = apps.get_model("calculator", "BankTariff")
    TaxSettings = apps.get_model("calculator", "TaxSettings")
    BankTariff.objects.filter(bank="tbank").delete()
    TaxSettings.objects.filter(year=2026).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("calculator", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_initial_data, remove_initial_data),
    ]
