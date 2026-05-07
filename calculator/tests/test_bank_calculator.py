"""
Unit-тесты для банковского калькулятора.

Покрываемые сценарии:
- вывод = 0
- вывод точно в лимите (граничное значение)
- вывод на 1 ₽ больше лимита
- попадание в первый тир (до 400к)
- попадание во второй тир (400к–1М)
- попадание в третий тир (свыше 1М)
- несколько операций вывода
- обслуживание бесплатное / платное
- поставщик в том же / другом банке
"""
import pytest
from decimal import Decimal

from calculator.services.bank_calculator import (
    calculate_withdrawal_commission,
    calculate_bank_commissions,
)

# ──────────────────────────────────────────────
# Конфигурация тарифа «Простой» Т-Банка
# ──────────────────────────────────────────────
SIMPLE_CONFIG = {
    "free_limit": 150_000,
    "fixed_fee_per_operation": 99,
    "tiers": [
        {"up_to": 400_000, "rate": 1.5},
        {"up_to": 1_000_000, "rate": 5.0},
        {"up_to": None, "rate": 15.0},
    ],
}


class TestWithdrawalCommission:
    """Тесты расчёта комиссии за вывод на личную карту."""

    def test_zero_amount(self):
        """Вывод 0 ₽ — комиссия 0."""
        result = calculate_withdrawal_commission(Decimal("0"), SIMPLE_CONFIG)
        assert result["total_commission"] == Decimal("0")

    def test_exactly_at_free_limit(self):
        """Вывод ровно 150 000 ₽ — попадает в бесплатный лимит, комиссия 0."""
        result = calculate_withdrawal_commission(Decimal("150000"), SIMPLE_CONFIG)
        assert result["total_commission"] == Decimal("0")
        assert result["percent_commission"] == Decimal("0")
        assert result["fixed_commission"] == Decimal("0")

    def test_one_ruble_over_limit(self):
        """Вывод 150 001 ₽ — минимальная комиссия: 1 ₽ × 1,5% + 99 ₽ = 99,02 ₽."""
        result = calculate_withdrawal_commission(Decimal("150001"), SIMPLE_CONFIG)
        # 1 ₽ × 1.5% = 0.015 → округление до 0.02, + 99 ₽ = 99.02
        assert result["total_commission"] == Decimal("99.02")
        assert result["fixed_commission"] == Decimal("99")

    def test_first_tier_boundary(self):
        """Вывод ровно 400 000 ₽ — 1-й тир целиком: 250 000 × 1,5% + 99 ₽."""
        result = calculate_withdrawal_commission(Decimal("400000"), SIMPLE_CONFIG)
        # 250 000 × 1.5% = 3 750 + 99 = 3 849
        assert result["percent_commission"] == Decimal("3750.00")
        assert result["total_commission"] == Decimal("3849.00")

    def test_second_tier(self):
        """Вывод 700 000 ₽ — захватывает 1-й и 2-й тиры."""
        result = calculate_withdrawal_commission(Decimal("700000"), SIMPLE_CONFIG)
        # 1-й тир: 250 000 × 1.5% = 3 750
        # 2-й тир: 300 000 × 5.0% = 15 000
        # фикс: 99
        # итого: 18 849
        assert result["percent_commission"] == Decimal("18750.00")
        assert result["total_commission"] == Decimal("18849.00")

    def test_second_tier_boundary(self):
        """Вывод ровно 1 000 000 ₽ — конец 2-го тира."""
        result = calculate_withdrawal_commission(Decimal("1000000"), SIMPLE_CONFIG)
        # 1-й: 250 000 × 1.5% = 3 750
        # 2-й: 600 000 × 5.0% = 30 000
        # фикс: 99
        # итого: 33 849
        assert result["percent_commission"] == Decimal("33750.00")
        assert result["total_commission"] == Decimal("33849.00")

    def test_third_tier(self):
        """Вывод 1 500 000 ₽ — захватывает все три тира."""
        result = calculate_withdrawal_commission(Decimal("1500000"), SIMPLE_CONFIG)
        # 1-й: 250 000 × 1.5% = 3 750
        # 2-й: 600 000 × 5.0% = 30 000
        # 3-й: 500 000 × 15.0% = 75 000
        # фикс: 99
        # итого: 108 849
        assert result["percent_commission"] == Decimal("108750.00")
        assert result["total_commission"] == Decimal("108849.00")

    def test_multiple_operations(self):
        """Несколько операций вывода — фиксированная часть умножается на количество."""
        result = calculate_withdrawal_commission(
            Decimal("200000"), SIMPLE_CONFIG, num_operations=3
        )
        # (200 000 - 150 000) × 1.5% = 750
        # фикс: 99 × 3 = 297
        # итого: 1 047
        assert result["fixed_commission"] == Decimal("297")
        assert result["total_commission"] == Decimal("1047.00")

    def test_no_tiers_config(self):
        """Если тиры не заданы — только фиксированная плата (защита от ошибки конфига)."""
        config = {"free_limit": 100_000, "fixed_fee_per_operation": 50, "tiers": []}
        result = calculate_withdrawal_commission(Decimal("200000"), config)
        # нет тиров → процентная часть = 0, только фикс
        assert result["percent_commission"] == Decimal("0")
        assert result["fixed_commission"] == Decimal("50")


class TestBankCommissions:
    """Интеграционные тесты полного расчёта банковских комиссий."""

    BASE_KWARGS = dict(
        tariff_maintenance_fee=Decimal("490"),
        tariff_outgoing_same_bank=Decimal("0"),
        tariff_outgoing_other_bank=Decimal("49"),
        tariff_withdrawal_config=SIMPLE_CONFIG,
    )

    def test_all_free(self):
        """Все условия бесплатного тарифа выполнены, поставщик в том же банке, вывод 0."""
        result = calculate_bank_commissions(
            purchase_amount=Decimal("100000"),
            supplier_in_same_bank=True,
            maintenance_condition_met=True,
            withdrawal_amount=Decimal("0"),
            withdrawal_operations=1,
            **self.BASE_KWARGS,
        )
        assert result["maintenance"] == Decimal("0")
        assert result["outgoing"] == Decimal("0")
        assert result["withdrawal"]["total_commission"] == Decimal("0")
        assert result["total"] == Decimal("0")

    def test_maintenance_paid(self):
        """Условие обслуживания не выполнено — 490 ₽ списывается."""
        result = calculate_bank_commissions(
            purchase_amount=Decimal("50000"),
            supplier_in_same_bank=True,
            maintenance_condition_met=False,
            withdrawal_amount=Decimal("0"),
            withdrawal_operations=1,
            **self.BASE_KWARGS,
        )
        assert result["maintenance"] == Decimal("490")

    def test_other_bank_fee(self):
        """Поставщик в другом банке — 49 ₽ комиссия."""
        result = calculate_bank_commissions(
            purchase_amount=Decimal("50000"),
            supplier_in_same_bank=False,
            maintenance_condition_met=True,
            withdrawal_amount=Decimal("0"),
            withdrawal_operations=1,
            **self.BASE_KWARGS,
        )
        assert result["outgoing"] == Decimal("49")

    def test_full_scenario(self):
        """Полный сценарий: обслуживание + другой банк + вывод с комиссией."""
        result = calculate_bank_commissions(
            purchase_amount=Decimal("100000"),
            supplier_in_same_bank=False,
            maintenance_condition_met=False,
            withdrawal_amount=Decimal("200000"),
            withdrawal_operations=1,
            **self.BASE_KWARGS,
        )
        # обслуживание: 490
        # исходящий: 49
        # вывод: 750 + 99 = 849
        # итого: 1 388
        assert result["maintenance"] == Decimal("490")
        assert result["outgoing"] == Decimal("49")
        assert result["total"] == Decimal("1388.00")
