"""
Unit-тесты для главного калькулятора прибыли.

Проверяет:
- calculate_net_profit: корректность итоговой прибыли
- find_required_sale_price: обратная задача (цена для желаемой прибыли)
- calculate_breakeven: точка безубыточности
- generate_recommendations: наличие рекомендаций при разных условиях
"""
import pytest
from decimal import Decimal

from calculator.services.profit_calculator import (
    calculate_net_profit,
    find_required_sale_price,
    calculate_breakeven,
    generate_recommendations,
)

# ──────────────────────────────────────────────
# Общие фикстуры
# ──────────────────────────────────────────────

TBANK_WITHDRAWAL_CONFIG = {
    "free_limit": 150_000,
    "fixed_fee_per_operation": 99,
    "tiers": [
        {"up_to": 400_000, "rate": 1.5},
        {"up_to": 1_000_000, "rate": 5.0},
        {"up_to": None, "rate": 15.0},
    ],
}

BANK_KWARGS_FREE = dict(
    supplier_in_same_bank=True,
    maintenance_condition_met=True,
    withdrawal_amount=Decimal("0"),
    withdrawal_operations=1,
    tariff_maintenance_fee=Decimal("490"),
    tariff_outgoing_same_bank=Decimal("0"),
    tariff_outgoing_other_bank=Decimal("49"),
    tariff_withdrawal_config=TBANK_WITHDRAWAL_CONFIG,
)

INSURANCE_KWARGS = dict(
    fixed_insurance_annual=Decimal("49500"),
    additional_threshold_annual=Decimal("300000"),
    additional_rate_percent=Decimal("1"),
)


class TestCalculateNetProfit:
    """Расчёт чистой прибыли при заданной цене продажи."""

    def test_usn6_no_bank_fee(self):
        """УСН 6%, все банковские условия выполнены, вывод = 0."""
        result = calculate_net_profit(
            sale_price=Decimal("200000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        # Страховые взносы: 4 125 фикс + 1% от (200 000 - 25 000) = 1 750 → 5 875
        # Налог (усн6): 200 000 × 6% = 12 000; вычет: min(5 875, 12 000) = 5 875 → 6 125
        # Прибыль: 200 000 - 100 000 - 5 875 - 6 125 - 0 = 88 000
        assert result["net_profit"] == Decimal("88000.00")
        assert result["margin"] > Decimal("40")

    def test_usn6_profit_positive(self):
        """При продаже выше закупки прибыль должна быть > 0."""
        result = calculate_net_profit(
            sale_price=Decimal("150000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert result["net_profit"] > Decimal("0")

    def test_sale_equals_purchase_is_unprofitable(self):
        """Продажа по цене закупки = убыток (налоги и взносы всегда есть)."""
        result = calculate_net_profit(
            sale_price=Decimal("100000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert result["net_profit"] < Decimal("0")

    def test_usn15_with_loss(self):
        """УСН 15%: расходы превышают доходы — применяется минимальный налог."""
        result = calculate_net_profit(
            sale_price=Decimal("100000"),
            purchase_amount=Decimal("120000"),
            tax_system="usn15",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert result["tax"]["is_minimum_tax"]
        assert result["net_profit"] < Decimal("0")

    def test_withdrawal_commission_included(self):
        """Комиссия за вывод 200 000 ₽ должна снизить прибыль."""
        bank_with_withdrawal = {**BANK_KWARGS_FREE, "withdrawal_amount": Decimal("200000")}

        result_no_w = calculate_net_profit(
            sale_price=Decimal("300000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        result_with_w = calculate_net_profit(
            sale_price=Decimal("300000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=bank_with_withdrawal,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert result_with_w["net_profit"] < result_no_w["net_profit"]


class TestFindRequiredSalePrice:
    """Обратная задача: поиск цены для достижения желаемой прибыли."""

    def test_finds_correct_price_usn6(self):
        """Найденная цена продажи даёт желаемую прибыль с точностью 10 коп."""
        desired = Decimal("30000")
        sale_price = find_required_sale_price(
            desired_net_profit=desired,
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        result = calculate_net_profit(
            sale_price=sale_price,
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert abs(result["net_profit"] - desired) <= Decimal("0.10")

    def test_finds_correct_price_usn15(self):
        """УСН 15%: обратная задача работает корректно."""
        desired = Decimal("20000")
        sale_price = find_required_sale_price(
            desired_net_profit=desired,
            purchase_amount=Decimal("80000"),
            tax_system="usn15",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        result = calculate_net_profit(
            sale_price=sale_price,
            purchase_amount=Decimal("80000"),
            tax_system="usn15",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert abs(result["net_profit"] - desired) <= Decimal("0.10")

    def test_zero_desired_profit(self):
        """Желаемая прибыль = 0 — должна вернуть цену > закупки."""
        sale_price = find_required_sale_price(
            desired_net_profit=Decimal("0"),
            purchase_amount=Decimal("50000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert sale_price > Decimal("50000")

    def test_result_greater_than_purchase(self):
        """Цена продажи всегда больше закупки (налоги и взносы > 0)."""
        sale_price = find_required_sale_price(
            desired_net_profit=Decimal("10000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert sale_price > Decimal("100000")


class TestCalculateBreakeven:
    """Точка безубыточности."""

    def test_breakeven_is_profitable_at_higher_price(self):
        """При цене выше точки безубыточности прибыль > 0."""
        breakeven = calculate_breakeven(
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        result_above = calculate_net_profit(
            sale_price=breakeven + Decimal("1000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        assert result_above["net_profit"] > Decimal("0")

    def test_breakeven_greater_than_purchase(self):
        """Точка безубыточности всегда выше цены закупки."""
        breakeven = calculate_breakeven(
            purchase_amount=Decimal("50000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("5000"),
        )
        assert breakeven > Decimal("50000")


class TestGenerateRecommendations:
    """Рекомендации по оптимизации."""

    def test_negative_profit_gives_danger(self):
        """Убыточная сделка → предупреждение."""
        result = calculate_net_profit(
            sale_price=Decimal("90000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        recs = generate_recommendations(result, "usn6")
        types = [r["type"] for r in recs]
        assert "danger" in types

    def test_maintenance_fee_gives_warning(self):
        """Платное обслуживание → рекомендация."""
        bank_with_fee = {**BANK_KWARGS_FREE, "maintenance_condition_met": False}
        result = calculate_net_profit(
            sale_price=Decimal("200000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=bank_with_fee,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        recs = generate_recommendations(result, "usn6")
        texts = " ".join(r["text"] for r in recs)
        assert "490" in texts or "обслуживани" in texts.lower()

    def test_usn6_insurance_deduction_hint(self):
        """УСН 6% → подсказка об уплате взносов ежеквартально."""
        result = calculate_net_profit(
            sale_price=Decimal("200000"),
            purchase_amount=Decimal("100000"),
            tax_system="usn6",
            bank_kwargs=BANK_KWARGS_FREE,
            insurance_kwargs=INSURANCE_KWARGS,
            additional_expenses=Decimal("0"),
        )
        recs = generate_recommendations(result, "usn6")
        texts = " ".join(r["text"] for r in recs)
        assert "взнос" in texts.lower() or "вычет" in texts.lower()
