"""
Главный сервис расчёта прибыли ИП.

Оркестрирует bank_calculator и tax_calculator, решает обратную задачу
(необходимая сумма продажи для достижения желаемой чистой прибыли).
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .bank_calculator import calculate_bank_commissions
from .tax_calculator import calculate_tax, calculate_monthly_insurance, TaxSystem


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_net_profit(
    sale_price: Decimal,
    purchase_amount: Decimal,
    tax_system: TaxSystem,
    bank_kwargs: dict[str, Any],
    insurance_kwargs: dict[str, Any],
    additional_expenses: Decimal,
    has_employees: bool = False,
) -> dict[str, Any]:
    """
    Рассчитывает чистую прибыль при заданной цене продажи.

    Args:
        sale_price: цена продажи (выручка = доход ИП)
        purchase_amount: сумма закупки (расход)
        tax_system: система налогообложения
        bank_kwargs: параметры для calculate_bank_commissions (без purchase_amount)
        insurance_kwargs: параметры для calculate_monthly_insurance
        additional_expenses: прочие ручные расходы (гарантии, ЭТП и т.д.)
        has_employees: наличие сотрудников (влияет на вычет УСН 6%)

    Returns:
        Подробный словарь с разбивкой всех статей расходов и итоговой прибылью.
    """
    # 1. Банковские комиссии (обслуживание может зависеть от выручки в режиме rate)
    bank = calculate_bank_commissions(
        purchase_amount=purchase_amount,
        revenue=sale_price,
        **bank_kwargs,
    )
    bank_total = bank["total"]

    # 2. Страховые взносы (зависят от выручки через дополнительный 1%)
    ins = calculate_monthly_insurance(
        monthly_revenue=sale_price,
        **insurance_kwargs,
    )
    insurance_total = ins["total"]

    # 3. Суммарные расходы для УСН 15% и ОСНО
    # (закупка + банк + взносы + прочие)
    total_expenses = _q(purchase_amount + bank_total + insurance_total + additional_expenses)

    # 4. Налог
    tax = calculate_tax(
        tax_system=tax_system,
        revenue=sale_price,
        expenses=total_expenses,
        insurance_total=insurance_total,
        has_employees=has_employees,
    )
    tax_amount = tax["net_tax"]

    # 5. Итоговая прибыль
    # Для УСН 6%: взносы уже вычтены из налога, поэтому платим:
    #   - закупку, - банк, - налог (после вычета взносов), - взносы, - прочие
    net_profit = _q(sale_price - purchase_amount - bank_total - insurance_total - tax_amount - additional_expenses)

    # 6. Эффективная ставка расходов (все расходы / выручка)
    total_costs = _q(purchase_amount + bank_total + insurance_total + tax_amount + additional_expenses)
    effective_rate = _q((total_costs / sale_price * 100)) if sale_price > 0 else Decimal("0")

    # 7. Маржа (прибыль / выручка)
    margin = _q((net_profit / sale_price * 100)) if sale_price > 0 else Decimal("0")

    return {
        "sale_price": _q(sale_price),
        "purchase_amount": _q(purchase_amount),
        "bank": bank,
        "insurance": ins,
        "tax": tax,
        "additional_expenses": _q(additional_expenses),
        "total_costs": total_costs,
        "net_profit": net_profit,
        "effective_expense_rate": effective_rate,
        "margin": margin,
    }


def find_required_sale_price(
    desired_net_profit: Decimal,
    purchase_amount: Decimal,
    tax_system: TaxSystem,
    bank_kwargs: dict[str, Any],
    insurance_kwargs: dict[str, Any],
    additional_expenses: Decimal,
    has_employees: bool = False,
    max_iterations: int = 200,
    tolerance: Decimal = Decimal("0.10"),
) -> Decimal:
    """
    Методом бисекции находит сумму продажи, при которой достигается
    желаемая чистая прибыль.

    Функция net_profit(sale_price) монотонно возрастает, что гарантирует
    сходимость бисекции.

    Args:
        desired_net_profit: целевая чистая прибыль (желаемый заработок)
        tolerance: точность до рублей (по умолчанию 10 копеек)
    """
    # Нижняя граница: продаём по цене закупки (заведомо убыточно)
    low = purchase_amount
    # Верхняя граница: многократный запас
    high = purchase_amount + desired_net_profit * Decimal("10") + Decimal("50000")

    # Убеждаемся, что на верхней границе прибыль превышает целевую
    for _ in range(30):
        result_high = calculate_net_profit(
            sale_price=high,
            purchase_amount=purchase_amount,
            tax_system=tax_system,
            bank_kwargs=bank_kwargs,
            insurance_kwargs=insurance_kwargs,
            additional_expenses=additional_expenses,
            has_employees=has_employees,
        )
        if result_high["net_profit"] >= desired_net_profit:
            break
        high *= Decimal("2")

    # Бисекция
    for _ in range(max_iterations):
        mid = _q((low + high) / 2)
        result = calculate_net_profit(
            sale_price=mid,
            purchase_amount=purchase_amount,
            tax_system=tax_system,
            bank_kwargs=bank_kwargs,
            insurance_kwargs=insurance_kwargs,
            additional_expenses=additional_expenses,
            has_employees=has_employees,
        )
        diff = result["net_profit"] - desired_net_profit

        if abs(diff) <= tolerance:
            return mid

        if diff < 0:
            low = mid
        else:
            high = mid

    return mid


def calculate_breakeven(
    purchase_amount: Decimal,
    tax_system: TaxSystem,
    bank_kwargs: dict[str, Any],
    insurance_kwargs: dict[str, Any],
    additional_expenses: Decimal,
    has_employees: bool = False,
) -> Decimal:
    """
    Рассчитывает точку безубыточности (сумму продажи при нулевой прибыли).
    """
    return find_required_sale_price(
        desired_net_profit=Decimal("0"),
        purchase_amount=purchase_amount,
        tax_system=tax_system,
        bank_kwargs=bank_kwargs,
        insurance_kwargs=insurance_kwargs,
        additional_expenses=additional_expenses,
        has_employees=has_employees,
    )


def compare_tax_systems(
    sale_price: Decimal,
    purchase_amount: Decimal,
    additional_expenses: Decimal,
    bank_kwargs: dict[str, Any],
    insurance_kwargs: dict[str, Any],
    has_employees: bool,
    current_tax_system: TaxSystem,
    expected_monthly_revenue: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """
    Сравнивает УСН 6% и УСН 15% для одних и тех же параметров сделки.
    Вычисляет точку безразличия — месячный оборот, после которого меняется выгода.

    Математика точки безразличия (при обороте > 300 000 ₽/год):
      Нагрузка (6%) = max(6% × D, I(D))
      Нагрузка (15%) = 15% × (D × (1-e) - I(D)) + I(D)
      где I(D) = 49 500 + 1% × (D - 300 000) — взносы
          e — доля базовых расходов в выручке (закупка + прочее)

      При 0.06D > I(D): 0.06D = 0.15(D(1-e) - I(D)) + I(D)
      → D = 39 525 / (0.15e - 0.0985)
      Знаменатель > 0 при e > 65.7% — это и есть порог доли расходов.
    """
    # Считаем результат под обеими системами с теми же параметрами
    result_6 = calculate_net_profit(
        sale_price=sale_price,
        purchase_amount=purchase_amount,
        tax_system="usn6",
        bank_kwargs=bank_kwargs,
        insurance_kwargs=insurance_kwargs,
        additional_expenses=additional_expenses,
        has_employees=has_employees,
    )
    result_15 = calculate_net_profit(
        sale_price=sale_price,
        purchase_amount=purchase_amount,
        tax_system="usn15",
        bank_kwargs=bank_kwargs,
        insurance_kwargs=insurance_kwargs,
        additional_expenses=additional_expenses,
        has_employees=has_employees,
    )

    # Доля базовых расходов в выручке (без налога, взносов, банка — они зависят от системы)
    base_expenses = purchase_amount + additional_expenses
    e = (base_expenses / sale_price) if sale_price > 0 else Decimal("0")

    # ── Точка безразличия ────────────────────────────────────────────────
    # При e < 65.67% → знаменатель ≤ 0 → УСН 6% всегда выгоднее при высокой выручке
    # При e > 65.67% → есть конкретный порог оборота
    CROSSOVER_EXPENSE_THRESHOLD = Decimal("0.6567")

    denom = Decimal("0.15") * e - Decimal("0.0985")
    if e <= CROSSOVER_EXPENSE_THRESHOLD or denom <= 0:
        crossover_annual  = None
        crossover_monthly = None
        crossover_exists  = False
    else:
        crossover_annual  = _q(Decimal("39525") / denom)
        crossover_monthly = _q(crossover_annual / 12)
        crossover_exists  = True

    # ── Порог оборота, при котором взносы перестают закрывать налог УСН 6% ──
    # 6% × D = 49 500 + 1% × (D - 300 000)  →  D = 930 000 ₽/год = 77 500 ₽/мес
    FREE_TAX_ANNUAL  = Decimal("930000")
    FREE_TAX_MONTHLY = Decimal("77500")

    burden_6  = _q(result_6["tax"]["net_tax"]  + result_6["insurance"]["total"])
    burden_15 = _q(result_15["tax"]["net_tax"] + result_15["insurance"]["total"])

    better = "usn6" if result_6["net_profit"] >= result_15["net_profit"] else "usn15"
    profit_diff = _q(abs(result_6["net_profit"] - result_15["net_profit"]))

    # Сравниваем ожидаемый оборот с точкой безразличия
    monthly_vs_crossover: str | None = None
    if crossover_exists and expected_monthly_revenue > 0:
        if expected_monthly_revenue < crossover_monthly:
            monthly_vs_crossover = "below"   # ещё выгоднее УСН 6%
        else:
            monthly_vs_crossover = "above"   # пора смотреть на УСН 15%

    return {
        "usn6":  result_6,
        "usn15": result_15,
        "burden_6":  burden_6,
        "burden_15": burden_15,
        "current":  current_tax_system,
        "better":   better,
        "profit_diff": profit_diff,
        "expense_ratio_pct": _q(e * 100),
        "crossover_exists":  crossover_exists,
        "crossover_annual":  crossover_annual,
        "crossover_monthly": crossover_monthly,
        "free_tax_monthly":  FREE_TAX_MONTHLY,
        "free_tax_annual":   FREE_TAX_ANNUAL,
        "monthly_vs_crossover": monthly_vs_crossover,
        "expected_monthly_revenue": expected_monthly_revenue,
    }


def generate_recommendations(result: dict[str, Any], tax_system: TaxSystem) -> list[dict[str, str]]:
    """
    Генерирует список рекомендаций по оптимизации расходов.

    Returns:
        Список словарей {"type": "success"|"warning"|"danger", "text": "..."}
    """
    recommendations = []
    bank = result["bank"]
    ins = result["insurance"]
    effective_rate = result["effective_expense_rate"]
    net_profit = result["net_profit"]

    # Чистая прибыль отрицательная
    if net_profit < 0:
        recommendations.append({
            "type": "danger",
            "text": "⚠️ Сделка убыточна. Увеличьте цену продажи или снизьте расходы.",
        })

    # Высокая ставка расходов
    if effective_rate > Decimal("40"):
        recommendations.append({
            "type": "danger",
            "text": f"Совокупные расходы составляют {effective_rate}% от выручки — это высокий уровень. "
                    "Пересмотрите ценообразование.",
        })
    elif effective_rate > Decimal("25"):
        recommendations.append({
            "type": "warning",
            "text": f"Совокупные расходы: {effective_rate}% от выручки. "
                    "Рекомендуем оптимизировать структуру затрат.",
        })

    # Обслуживание счёта
    if bank["maintenance"] > 0:
        if bank.get("maintenance_mode") == "rate":
            recommendations.append({
                "type": "warning",
                "text": f"Обслуживание счёта: {bank['maintenance_rate_pct']}% от выручки сделки ({bank['maintenance']} ₽). "
                        "Выполните условие банка (покупки по бизнес-карте от 150 000 ₽) — обслуживание станет бесплатным.",
            })
        else:
            recommendations.append({
                "type": "warning",
                "text": f"Списывается {bank['maintenance']} ₽/мес за обслуживание счёта. "
                        "Выполните условие банка (покупки по бизнес-карте от 150 000 ₽) — обслуживание станет бесплатным.",
            })

    # Высокая комиссия за вывод
    withdrawal = bank["withdrawal"]
    if withdrawal["total_commission"] > Decimal("500"):
        recommendations.append({
            "type": "warning",
            "text": f"Комиссия за вывод: {withdrawal['total_commission']} ₽. "
                    "Рассмотрите вывод частями или переход на тариф с большим бесплатным лимитом.",
        })

    # Вычет взносов при УСН 6%
    if tax_system == "usn6" and ins["total"] > 0:
        recommendations.append({
            "type": "success",
            "text": f"При УСН 6% страховые взносы ({ins['total']} ₽) вычтены из налога. "
                    "Уплачивайте взносы равными долями ежеквартально для максимального вычета.",
        })

    # Минимальный налог УСН 15%
    tax = result["tax"]
    if tax_system == "usn15" and tax.get("is_minimum_tax"):
        recommendations.append({
            "type": "warning",
            "text": "Применён минимальный налог 1% (расходы превысили доходы). "
                    "Убедитесь, что все расходы документально подтверждены.",
        })

    # Если всё хорошо
    if not recommendations:
        recommendations.append({
            "type": "success",
            "text": "Структура расходов оптимальна. Прибыль в норме.",
        })

    return recommendations
