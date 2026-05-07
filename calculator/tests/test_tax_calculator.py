"""
Unit-тесты для налогового калькулятора.

Покрываемые сценарии:
- УСН 6%: обычный, взносы полностью покрывают налог, с сотрудниками
- УСН 15%: обычный, убыток (минимальный налог), расходы = доходы
- НПД: физлица (4%), юрлица (6%)
- ОСНО: базовый расчёт
- Страховые взносы: фикс, дополнительный 1%, граничное значение
"""
import pytest
from decimal import Decimal

from calculator.services.tax_calculator import (
    calculate_usn6,
    calculate_usn15,
    calculate_npd,
    calculate_osno,
    calculate_monthly_insurance,
    calculate_tax,
)


class TestMonthlyInsurance:
    """Расчёт страховых взносов ИП."""

    KWARGS = dict(
        fixed_insurance_annual=Decimal("49500"),
        additional_threshold_annual=Decimal("300000"),
        additional_rate_percent=Decimal("1"),
    )

    def test_fixed_only_below_threshold(self):
        """Доход меньше порога — только фиксированная часть."""
        result = calculate_monthly_insurance(
            monthly_revenue=Decimal("10000"), **self.KWARGS
        )
        assert result["fixed"] == Decimal("4125.00")  # 49500/12
        assert result["additional"] == Decimal("0")
        assert result["total"] == Decimal("4125.00")

    def test_exactly_at_threshold(self):
        """Доход ровно на пороге (25 000 ₽/мес = 300 000/12) — доп. взнос = 0."""
        result = calculate_monthly_insurance(
            monthly_revenue=Decimal("25000"), **self.KWARGS
        )
        assert result["additional"] == Decimal("0")

    def test_additional_above_threshold(self):
        """Доход 125 000 ₽ — дополнительный 1% от (125 000 - 25 000) = 1 000 ₽."""
        result = calculate_monthly_insurance(
            monthly_revenue=Decimal("125000"), **self.KWARGS
        )
        assert result["additional"] == Decimal("1000.00")
        assert result["total"] == Decimal("5125.00")

    def test_zero_revenue(self):
        """Нулевой доход — только фиксированная часть."""
        result = calculate_monthly_insurance(
            monthly_revenue=Decimal("0"), **self.KWARGS
        )
        assert result["fixed"] == Decimal("4125.00")
        assert result["additional"] == Decimal("0")


class TestUSN6:
    """УСН 6% (доходы)."""

    def test_basic(self):
        """Стандартный расчёт: выручка 100 000, взносы 4 000."""
        result = calculate_usn6(
            revenue=Decimal("100000"),
            insurance_total=Decimal("4000"),
            has_employees=False,
        )
        # Налог: 100 000 × 6% = 6 000
        # Вычет: min(4 000, 6 000) = 4 000
        # К уплате: 6 000 - 4 000 = 2 000
        assert result["gross_tax"] == Decimal("6000.00")
        assert result["deduction"] == Decimal("4000.00")
        assert result["net_tax"] == Decimal("2000.00")

    def test_insurance_fully_covers_tax(self):
        """Взносы превышают налог — налог = 0 (только без сотрудников)."""
        result = calculate_usn6(
            revenue=Decimal("50000"),
            insurance_total=Decimal("4125"),  # фикс. взносы за месяц
            has_employees=False,
        )
        # Налог: 50 000 × 6% = 3 000
        # Вычет: min(4 125, 3 000) = 3 000 (ограничен 100% налога)
        # К уплате: 0
        assert result["gross_tax"] == Decimal("3000.00")
        assert result["net_tax"] == Decimal("0")

    def test_with_employees_50pct_limit(self):
        """С сотрудниками вычет ограничен 50% налога."""
        result = calculate_usn6(
            revenue=Decimal("200000"),
            insurance_total=Decimal("8000"),
            has_employees=True,
        )
        # Налог: 200 000 × 6% = 12 000
        # Максимальный вычет: 12 000 × 50% = 6 000
        # Фактический вычет: min(8 000, 6 000) = 6 000
        # К уплате: 12 000 - 6 000 = 6 000
        assert result["gross_tax"] == Decimal("12000.00")
        assert result["deduction"] == Decimal("6000.00")
        assert result["net_tax"] == Decimal("6000.00")

    def test_zero_revenue(self):
        """Нулевая выручка — налог 0."""
        result = calculate_usn6(
            revenue=Decimal("0"),
            insurance_total=Decimal("4125"),
            has_employees=False,
        )
        assert result["net_tax"] == Decimal("0")


class TestUSN15:
    """УСН 15% (доходы минус расходы)."""

    def test_profitable(self):
        """Прибыльная сделка: выручка 200 000, расходы 100 000."""
        result = calculate_usn15(
            revenue=Decimal("200000"),
            expenses=Decimal("100000"),
        )
        # База: 100 000
        # Налог: 100 000 × 15% = 15 000
        # Мин. налог: 200 000 × 1% = 2 000
        # К уплате: max(15 000, 2 000) = 15 000
        assert result["tax_base"] == Decimal("100000.00")
        assert result["regular_tax"] == Decimal("15000.00")
        assert result["net_tax"] == Decimal("15000.00")
        assert not result["is_minimum_tax"]

    def test_loss_minimum_tax(self):
        """Убыток: расходы > доходов — применяется минимальный налог 1%."""
        result = calculate_usn15(
            revenue=Decimal("100000"),
            expenses=Decimal("150000"),
        )
        # База: max(100 000 - 150 000, 0) = 0
        # Обычный налог: 0 × 15% = 0
        # Мин. налог: 100 000 × 1% = 1 000
        # К уплате: 1 000
        assert result["tax_base"] == Decimal("0")
        assert result["regular_tax"] == Decimal("0")
        assert result["minimum_tax"] == Decimal("1000.00")
        assert result["net_tax"] == Decimal("1000.00")
        assert result["is_minimum_tax"]

    def test_expenses_equal_revenue(self):
        """Расходы = доходам — применяется минимальный налог."""
        result = calculate_usn15(
            revenue=Decimal("100000"),
            expenses=Decimal("100000"),
        )
        assert result["regular_tax"] == Decimal("0")
        assert result["net_tax"] == Decimal("1000.00")
        assert result["is_minimum_tax"]

    def test_low_margin_minimum_tax(self):
        """Маленькая маржа, обычный налог ниже минимального."""
        result = calculate_usn15(
            revenue=Decimal("100000"),
            expenses=Decimal("95000"),
        )
        # База: 5 000; обычный: 750; мин.: 1 000 → применяем 1 000
        assert result["regular_tax"] == Decimal("750.00")
        assert result["minimum_tax"] == Decimal("1000.00")
        assert result["net_tax"] == Decimal("1000.00")
        assert result["is_minimum_tax"]

    def test_zero_revenue(self):
        """Нулевая выручка — минимальный налог тоже 0."""
        result = calculate_usn15(
            revenue=Decimal("0"),
            expenses=Decimal("0"),
        )
        assert result["net_tax"] == Decimal("0")


class TestNPD:
    """НПД (налог на профессиональный доход)."""

    def test_individual_4pct(self):
        """4% от физлиц."""
        result = calculate_npd(revenue=Decimal("100000"), client_type="individual")
        assert result["net_tax"] == Decimal("4000.00")

    def test_legal_6pct(self):
        """6% от юрлиц/ИП."""
        result = calculate_npd(revenue=Decimal("100000"), client_type="legal")
        assert result["net_tax"] == Decimal("6000.00")

    def test_zero_revenue(self):
        result = calculate_npd(revenue=Decimal("0"), client_type="legal")
        assert result["net_tax"] == Decimal("0")


class TestOSNO:
    """ОСНО (упрощённый расчёт)."""

    def test_basic(self):
        """Базовый расчёт: выручка 500 000, расходы 300 000."""
        result = calculate_osno(
            revenue=Decimal("500000"),
            expenses=Decimal("300000"),
            vat_included_in_price=False,
        )
        # НДС с продажи: 500 000 × 20% = 100 000
        # Входящий НДС: 300 000 × 20/120 = 50 000
        # НДС к уплате: 100 000 - 50 000 = 50 000
        # Прибыль до НДФЛ: 500 000 - 300 000 = 200 000
        # НДФЛ: 200 000 × 13% = 26 000
        assert result["vat_payable"] == Decimal("50000.00")
        assert result["ndfl"] == Decimal("26000.00")
        assert result["net_tax"] == Decimal("76000.00")

    def test_loss_no_ndfl(self):
        """Убыток — НДФЛ не начисляется (не может быть отрицательным)."""
        result = calculate_osno(
            revenue=Decimal("100000"),
            expenses=Decimal("200000"),
            vat_included_in_price=False,
        )
        assert result["ndfl"] == Decimal("0")


class TestCalculateTax:
    """Универсальная функция calculate_tax."""

    def test_routes_usn6(self):
        result = calculate_tax(
            tax_system="usn6",
            revenue=Decimal("100000"),
            expenses=Decimal("50000"),
            insurance_total=Decimal("4000"),
        )
        assert "gross_tax" in result

    def test_routes_usn15(self):
        result = calculate_tax(
            tax_system="usn15",
            revenue=Decimal("100000"),
            expenses=Decimal("50000"),
            insurance_total=Decimal("4000"),
        )
        assert "tax_base" in result

    def test_routes_npd_individual(self):
        result = calculate_tax(
            tax_system="npd_individual",
            revenue=Decimal("100000"),
            expenses=Decimal("0"),
            insurance_total=Decimal("0"),
        )
        assert result["net_tax"] == Decimal("4000.00")

    def test_unknown_system_raises(self):
        with pytest.raises(ValueError, match="Неизвестная система"):
            calculate_tax(
                tax_system="unknown",  # type: ignore
                revenue=Decimal("100000"),
                expenses=Decimal("0"),
                insurance_total=Decimal("0"),
            )
