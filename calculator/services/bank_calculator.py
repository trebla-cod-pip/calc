"""
Расчёт банковских комиссий для ИП.

Поддерживает прогрессивную шкалу вывода средств (Т-Банк и другие).
Логика: каждый тир применяется к той части суммы, которая попадает в его диапазон.
"""
from decimal import Decimal
from typing import Any


def calculate_withdrawal_commission(
    amount: Decimal,
    config: dict[str, Any],
    num_operations: int = 1,
) -> dict[str, Decimal]:
    """
    Рассчитывает комиссию за вывод средств на личную карту.

    Прогрессивная шкала (пример Т-Банк «Простой»):
    - 0..150 000 ₽ — бесплатно
    - 150 001..400 000 ₽ — 1,5% от суммы в этом тире
    - 400 001..1 000 000 ₽ — 5% от суммы в этом тире
    - свыше 1 000 000 ₽ — 15% от суммы в этом тире
    + фиксированная часть (99 ₽) за операцию при превышении лимита

    Args:
        amount: сумма вывода, ₽
        config: конфигурация тарифа (поле withdrawal_config из BankTariff)
        num_operations: количество операций вывода за период

    Returns:
        Словарь с детальным расчётом.
    """
    amount = Decimal(str(amount))
    free_limit = Decimal(str(config.get("free_limit", 150_000)))
    fixed_fee = Decimal(str(config.get("fixed_fee_per_operation", 0)))
    tiers: list[dict] = config.get("tiers", [])

    if amount <= Decimal("0"):
        return {
            "amount": amount,
            "free_amount": Decimal("0"),
            "percent_commission": Decimal("0"),
            "fixed_commission": Decimal("0"),
            "total_commission": Decimal("0"),
        }

    if amount <= free_limit:
        return {
            "amount": amount,
            "free_amount": amount,
            "percent_commission": Decimal("0"),
            "fixed_commission": Decimal("0"),
            "total_commission": Decimal("0"),
        }

    # Считаем процентную часть по тирам
    percent_commission = Decimal("0")
    prev_boundary = free_limit  # начало первого тира
    remaining = amount - free_limit  # облагаемая сумма (сверх лимита)

    for tier in tiers:
        up_to = tier.get("up_to")
        rate = Decimal(str(tier["rate"])) / Decimal("100")

        if up_to is None:
            # Последний тир — без верхней границы
            percent_commission += remaining * rate
            remaining = Decimal("0")
            break

        tier_ceiling = Decimal(str(up_to))
        tier_size = tier_ceiling - prev_boundary          # объём этого тира
        tier_amount = min(remaining, tier_size)           # сколько попало в этот тир
        percent_commission += tier_amount * rate
        remaining -= tier_amount
        prev_boundary = tier_ceiling

        if remaining <= Decimal("0"):
            break

    # Фиксированная часть начисляется за каждую операцию вывода
    fixed_commission = fixed_fee * num_operations

    total = (percent_commission + fixed_commission).quantize(Decimal("0.01"))

    return {
        "amount": amount,
        "free_amount": free_limit,
        "percent_commission": percent_commission.quantize(Decimal("0.01")),
        "fixed_commission": fixed_commission.quantize(Decimal("0.01")),
        "total_commission": total,
    }


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def calculate_bank_commissions(
    *,
    purchase_amount: Decimal,
    revenue: Decimal = Decimal("0"),
    expected_monthly_revenue: Decimal = Decimal("0"),
    supplier_in_same_bank: bool,
    maintenance_condition_met: bool,
    withdrawal_amount: Decimal,
    withdrawal_operations: int,
    tariff_maintenance_fee: Decimal,
    tariff_outgoing_same_bank: Decimal,
    tariff_outgoing_other_bank: Decimal,
    tariff_withdrawal_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Рассчитывает все банковские комиссии за расчётный период (месяц).

    Args:
        purchase_amount: сумма закупки
        revenue: выручка по данной сделке (sale_price) — нужна для пропорционального расчёта обслуживания
        expected_monthly_revenue: ожидаемый месячный оборот.
            Если > 0 — комиссия за обслуживание «размазывается» по выручке
            пропорционально доле этой сделки вместо фиксированных 490 ₽/мес.
        supplier_in_same_bank: поставщик в том же банке
        maintenance_condition_met: условие бесплатного обслуживания выполнено
        withdrawal_*: параметры вывода на карту
        tariff_*: поля из выбранного BankTariff

    Returns:
        Словарь со всеми составляющими комиссий и итогом.
    """
    # 1. Обслуживание счёта
    if maintenance_condition_met:
        maintenance = Decimal("0")
        maintenance_mode = "free"
        maintenance_rate_pct = Decimal("0")
    elif expected_monthly_revenue > Decimal("0") and revenue > Decimal("0"):
        # Режим «по доле»: maintenance = ставка × выручка сделки
        maintenance_rate = tariff_maintenance_fee / expected_monthly_revenue
        maintenance = _q(revenue * maintenance_rate)
        maintenance_mode = "rate"
        maintenance_rate_pct = _q(maintenance_rate * 100)
    else:
        # Режим «абсолют»: полная месячная сумма
        maintenance = tariff_maintenance_fee
        maintenance_mode = "absolute"
        maintenance_rate_pct = Decimal("0")

    # 2. Исходящий платёж поставщику
    outgoing = tariff_outgoing_same_bank if supplier_in_same_bank else tariff_outgoing_other_bank

    # 3. Вывод на личную карту
    withdrawal_detail = calculate_withdrawal_commission(
        amount=withdrawal_amount,
        config=tariff_withdrawal_config,
        num_operations=withdrawal_operations,
    )
    withdrawal_commission = withdrawal_detail["total_commission"]

    total = maintenance + outgoing + withdrawal_commission

    return {
        "maintenance": _q(maintenance),
        "maintenance_mode": maintenance_mode,           # "free" | "absolute" | "rate"
        "maintenance_rate_pct": maintenance_rate_pct,   # % ставка (только в режиме rate)
        "outgoing": _q(outgoing),
        "withdrawal": withdrawal_detail,
        "total": _q(total),
    }
