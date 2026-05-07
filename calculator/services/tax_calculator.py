"""
Расчёт налогов и страховых взносов ИП в РФ (2026).

Поддерживаемые системы налогообложения:
- УСН 6%  (доходы)
- УСН 15% (доходы минус расходы)
- НПД     (налог на профессиональный доход)
- ОСНО    (упрощённый расчёт: НДФЛ 13%/15% + НДС 20%)

Все суммы — в рублях, расчётный период — месяц.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

TaxSystem = Literal["usn6", "usn15", "npd_individual", "npd_legal", "osno"]

# Ставки налогов
USN6_RATE = Decimal("0.06")
USN15_RATE = Decimal("0.15")
USN15_MIN_RATE = Decimal("0.01")   # минимальный налог 1% от дохода
NPD_INDIVIDUAL_RATE = Decimal("0.04")   # физлица
NPD_LEGAL_RATE = Decimal("0.06")        # юрлица и ИП
NDFL_RATE = Decimal("0.13")            # НДФЛ (до 5 млн ₽/год)
NDFL_HIGH_RATE = Decimal("0.15")       # НДФЛ (свыше 5 млн ₽/год)
NDFL_HIGH_THRESHOLD = Decimal("416667")  # 5 000 000 / 12 месяцев
VAT_RATE = Decimal("0.20")


def _q(value: Decimal) -> Decimal:
    """Округление до копеек."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_monthly_insurance(
    monthly_revenue: Decimal,
    fixed_insurance_annual: Decimal,
    additional_threshold_annual: Decimal,
    additional_rate_percent: Decimal,
    expected_monthly_revenue: Decimal = Decimal("0"),
) -> dict[str, Decimal]:
    """
    Страховые взносы ИП, отнесённые на конкретную сделку/период.

    Фиксированная часть (два режима):
    ─────────────────────────────────
    • Режим «абсолют» (expected_monthly_revenue = 0):
        fixed = annual / 12  — полная месячная сумма (4 125 ₽).
        Подходит для планирования всего месяца целиком.

    • Режим «по доле выручки» (expected_monthly_revenue > 0):
        Доля этой сделки в ожидаемой выручке = monthly_revenue / expected_monthly_revenue.
        fixed = (annual / 12) × (monthly_revenue / expected_monthly_revenue)
        = monthly_revenue × annual / (12 × expected_monthly_revenue)
        Таким образом взносы превращаются в % ставку, а не в фиксированную сумму,
        и не «раздувают» цену на мелкие сделки.

    Дополнительная часть (1% сверх порога):
        1% от той части выручки, которая превышает 300 000 ₽/год (25 000 ₽/мес).
        Уже пропорциональна выручке по природе — не меняется.

    Args:
        monthly_revenue: выручка по данной сделке / за расчётный период
        fixed_insurance_annual: фиксированные взносы за год (49 500 ₽)
        additional_threshold_annual: порог для 1% (300 000 ₽/год)
        additional_rate_percent: ставка доп. взноса (1 %)
        expected_monthly_revenue: ожидаемая ежемесячная выручка ИП;
            если > 0 — включает режим «по доле выручки»
    """
    if expected_monthly_revenue > Decimal("0"):
        # Режим «по доле»: взносы = ставка × выручка
        # Ставка = годовые взносы / ожидаемая годовая выручка
        fixed_rate = fixed_insurance_annual / (expected_monthly_revenue * 12)
        monthly_fixed = _q(monthly_revenue * fixed_rate)
        fixed_mode = "rate"
        fixed_rate_pct = _q(fixed_rate * 100)
    else:
        # Режим «абсолют»: полная 1/12 годовых взносов
        monthly_fixed = _q(fixed_insurance_annual / 12)
        fixed_mode = "absolute"
        fixed_rate_pct = Decimal("0")

    # Дополнительный взнос 1% — всегда пропорционален выручке
    monthly_threshold = additional_threshold_annual / 12
    additional_rate = additional_rate_percent / 100
    additional = Decimal("0")
    if monthly_revenue > monthly_threshold:
        additional = _q((monthly_revenue - monthly_threshold) * additional_rate)

    total = _q(monthly_fixed + additional)

    return {
        "fixed": monthly_fixed,
        "additional": additional,
        "total": total,
        "fixed_mode": fixed_mode,           # "absolute" | "rate"
        "fixed_rate_pct": fixed_rate_pct,   # % ставка (только в режиме rate)
        "expected_monthly_revenue": expected_monthly_revenue,
    }


def calculate_usn6(
    revenue: Decimal,
    insurance_total: Decimal,
    has_employees: bool = False,
) -> dict[str, Decimal]:
    """
    УСН 6% — налог с доходов.

    Вычет взносов:
    - без сотрудников: до 100% налога (налог ≥ 0)
    - с сотрудниками: до 50% налога

    Args:
        revenue: выручка (доход) за период
        insurance_total: уплаченные страховые взносы за период
        has_employees: есть ли наёмные работники
    """
    gross_tax = _q(revenue * USN6_RATE)

    if has_employees:
        # Вычет ограничен 50% налога
        max_deduction = _q(gross_tax * Decimal("0.5"))
    else:
        # Вычет до 100% (налог не может быть отрицательным)
        max_deduction = gross_tax

    deduction = min(insurance_total, max_deduction)
    net_tax = _q(max(gross_tax - deduction, Decimal("0")))

    return {
        "gross_tax": gross_tax,
        "deduction": _q(deduction),
        "net_tax": net_tax,
        "rate": USN6_RATE,
        "description": "УСН 6% (доходы)",
    }


def calculate_usn15(
    revenue: Decimal,
    expenses: Decimal,
) -> dict[str, Decimal]:
    """
    УСН 15% — налог с разницы «доходы минус расходы».

    Минимальный налог: 1% от дохода (применяется, если расчётный налог меньше).
    Страховые взносы включаются в расходы.

    Args:
        revenue: выручка за период
        expenses: расходы за период (закупка + взносы + комиссии + прочее)
    """
    tax_base = _q(max(revenue - expenses, Decimal("0")))
    regular_tax = _q(tax_base * USN15_RATE)
    minimum_tax = _q(revenue * USN15_MIN_RATE)

    # Применяем минимальный налог, если он больше расчётного
    net_tax = _q(max(regular_tax, minimum_tax))
    is_minimum = net_tax == minimum_tax and minimum_tax > regular_tax

    return {
        "tax_base": tax_base,
        "regular_tax": regular_tax,
        "minimum_tax": minimum_tax,
        "net_tax": net_tax,
        "is_minimum_tax": is_minimum,
        "rate": USN15_RATE,
        "description": "УСН 15% (доходы − расходы)",
    }


def calculate_npd(
    revenue: Decimal,
    client_type: Literal["individual", "legal"] = "legal",
) -> dict[str, Decimal]:
    """
    НПД — налог на профессиональный доход (самозанятые).

    Ставки: 4% от физлиц, 6% от юрлиц и ИП.
    Страховые взносы не обязательны.
    Ограничение: доход ≤ 2 400 000 ₽/год.

    Args:
        revenue: доход за период
        client_type: тип клиента («individual» — физлицо, «legal» — юрлицо/ИП)
    """
    rate = NPD_INDIVIDUAL_RATE if client_type == "individual" else NPD_LEGAL_RATE
    net_tax = _q(revenue * rate)

    return {
        "net_tax": net_tax,
        "rate": rate,
        "description": f"НПД {int(rate * 100)}% ({'физлицо' if client_type == 'individual' else 'юрлицо/ИП'})",
    }


def calculate_osno(
    revenue: Decimal,
    expenses: Decimal,
    vat_included_in_price: bool = False,
) -> dict[str, Decimal]:
    """
    ОСНО — упрощённый расчёт (НДФЛ + НДС).

    НДС: 20% от выручки (с учётом входящего НДС в расходах).
    НДФЛ: 13% (до 5 млн ₽/год) или 15% (свыше 5 млн ₽/год) от прибыли до налогов.

    Примечание: реальный ОСНО гораздо сложнее. Этот расчёт — ориентировочный.

    Args:
        revenue: выручка за период (с НДС, если vat_included_in_price=True)
        expenses: расходы за период (с НДС)
        vat_included_in_price: НДС уже включён в цену продажи
    """
    if vat_included_in_price:
        # Выделяем НДС из цены: НДС = Цена × 20/120
        vat_out = _q(revenue * Decimal("20") / Decimal("120"))
        revenue_net = revenue - vat_out
    else:
        vat_out = _q(revenue * VAT_RATE)
        revenue_net = revenue

    # Входящий НДС (в расходах)
    vat_in = _q(expenses * Decimal("20") / Decimal("120"))
    vat_payable = _q(max(vat_out - vat_in, Decimal("0")))

    # НДФЛ (упрощённо — от месячной прибыли)
    profit_before_ndfl = revenue_net - expenses
    ndfl_rate = NDFL_HIGH_RATE if profit_before_ndfl > NDFL_HIGH_THRESHOLD else NDFL_RATE
    ndfl = _q(max(profit_before_ndfl, Decimal("0")) * ndfl_rate)

    net_tax = _q(vat_payable + ndfl)

    return {
        "vat_out": vat_out,
        "vat_in": vat_in,
        "vat_payable": vat_payable,
        "ndfl": ndfl,
        "net_tax": net_tax,
        "rate": ndfl_rate + VAT_RATE,
        "description": f"ОСНО (НДФЛ {int(ndfl_rate * 100)}% + НДС 20%)",
    }


def calculate_tax(
    tax_system: TaxSystem,
    revenue: Decimal,
    expenses: Decimal,
    insurance_total: Decimal,
    has_employees: bool = False,
    npd_client_type: Literal["individual", "legal"] = "legal",
) -> dict:
    """
    Универсальная точка входа для расчёта налога по любой системе.

    Args:
        tax_system: система налогообложения
        revenue: выручка за период
        expenses: расходы (закупка + банковские комиссии + доп. расходы + взносы для УСН 15%)
        insurance_total: страховые взносы (используются для вычета в УСН 6%)
        has_employees: наличие сотрудников (влияет на вычет в УСН 6%)
        npd_client_type: тип клиента для НПД
    """
    if tax_system == "usn6":
        return calculate_usn6(revenue, insurance_total, has_employees)
    elif tax_system == "usn15":
        return calculate_usn15(revenue, expenses)
    elif tax_system in ("npd_individual", "npd_legal"):
        client = "individual" if tax_system == "npd_individual" else "legal"
        return calculate_npd(revenue, client)
    elif tax_system == "osno":
        return calculate_osno(revenue, expenses)
    else:
        raise ValueError(f"Неизвестная система налогообложения: {tax_system}")
