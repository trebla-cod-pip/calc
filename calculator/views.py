"""
Views калькулятора прибыли ИП.

Маршруты:
  GET  /calculator/                        — главный калькулятор
  POST /calculator/calculate/              — HTMX-расчёт прибыли
  GET  /calculator/tariffs/               — просмотр тарифов
  POST /calculator/tariffs/<pk>/set-default/
  GET  /calculator/requirements/          — потребности
  GET|POST /calculator/offers/            — КП поставщиков
  POST /calculator/offers/<pk>/delete/    — удаление КП
  GET  /calculator/deliveries/            — поставки
"""
from decimal import Decimal

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import CalculatorForm, RequirementForm, SupplierOfferForm, SupplierOfferEditForm
from .models import AppSettings, BankTariff, Delivery, DeliveryItem, Requirement, SupplierOffer, TaxSettings
from .services.profit_calculator import (
    calculate_net_profit,
    find_required_sale_price,
    calculate_breakeven,
    generate_recommendations,
    compare_tax_systems,
)
from .services.tax_calculator import TaxSystem


# ─────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────

def _get_tax_settings() -> TaxSettings:
    return TaxSettings.objects.order_by("-year").first()


def _build_insurance_kwargs(ts: TaxSettings, expected_monthly_revenue: Decimal = Decimal("0")) -> dict:
    return {
        "fixed_insurance_annual": ts.fixed_insurance_annual,
        "additional_threshold_annual": ts.additional_insurance_threshold,
        "additional_rate_percent": ts.additional_insurance_rate,
        "expected_monthly_revenue": expected_monthly_revenue,
    }


def _build_bank_kwargs(form_data: dict, tariff: BankTariff) -> dict:
    return {
        "supplier_in_same_bank": form_data["supplier_in_same_bank"],
        "maintenance_condition_met": form_data["maintenance_condition_met"],
        "withdrawal_amount": form_data["withdrawal_amount"],
        "withdrawal_operations": form_data["withdrawal_operations"],
        "expected_monthly_revenue": form_data.get("expected_monthly_revenue", Decimal("0")),
        "tariff_maintenance_fee": tariff.maintenance_fee,
        "tariff_outgoing_same_bank": tariff.outgoing_same_bank_fee,
        "tariff_outgoing_other_bank": tariff.outgoing_other_bank_fee,
        "tariff_withdrawal_config": tariff.withdrawal_config,
    }



# ─────────────────────────────────────────────────────
# Калькулятор прибыли
# ─────────────────────────────────────────────────────

def _parse_decimal_param(raw: str) -> Decimal | None:
    """Безопасно парсит числовой GET-параметр из русской или стандартной локали."""
    try:
        return Decimal(raw.strip().replace(" ", "").replace(",", "."))
    except Exception:
        return None


def index(request: HttpRequest) -> HttpResponse:
    """
    Главная страница калькулятора.

    GET ?purchase_price=1500&shipping=300 — подставляет данные из КП поставщика.
    """
    default_tariff = BankTariff.objects.filter(is_default=True, is_active=True).first()
    app_settings = AppSettings.get()
    initial: dict = {}

    if default_tariff:
        initial["tariff"] = default_tariff

    # Подставляем сохранённую выручку из AppSettings
    if app_settings.expected_monthly_revenue:
        initial["expected_monthly_revenue"] = app_settings.expected_monthly_revenue

    # Подстановка цены и доставки из страницы поставщиков
    prefilled = False
    if price := _parse_decimal_param(request.GET.get("purchase_price", "")):
        initial["purchase_amount"] = price
        prefilled = True
    if shipping := _parse_decimal_param(request.GET.get("shipping", "")):
        initial["expense_shipping"] = shipping

    form = CalculatorForm(initial=initial)
    return render(request, "calculator/index.html", {
        "form": form,
        "result": None,
        "prefilled_from_vendor": prefilled,
        "app_settings": app_settings,
    })


@require_http_methods(["POST"])
def save_settings(request: HttpRequest) -> HttpResponse:
    """HTMX: сохраняет ожидаемую выручку в AppSettings."""
    raw = request.POST.get("expected_monthly_revenue", "")
    value = _parse_decimal_param(raw) or Decimal("0")
    settings = AppSettings.get()
    settings.expected_monthly_revenue = value
    settings.save(update_fields=["expected_monthly_revenue"])
    # Возвращаем обновлённый виджет настроек
    return render(request, "calculator/partials/settings_saved.html", {
        "app_settings": settings,
    })


@require_http_methods(["POST"])
def calculate(request: HttpRequest) -> HttpResponse:
    """HTMX-расчёт прибыли."""
    form = CalculatorForm(request.POST)
    if not form.is_valid():
        if request.headers.get("HX-Request"):
            return render(request, "calculator/partials/errors.html", {"form": form})
        return render(request, "calculator/index.html", {"form": form, "result": None})

    data = form.cleaned_data
    tariff: BankTariff = data["tariff"]
    tax_system: TaxSystem = data["tax_system"]
    ts = _get_tax_settings()
    bank_kwargs = _build_bank_kwargs(data, tariff)
    insurance_kwargs = _build_insurance_kwargs(ts, data.get("expected_monthly_revenue", Decimal("0")))

    required_sale = find_required_sale_price(
        desired_net_profit=data["desired_profit"],
        purchase_amount=data["purchase_amount"],
        tax_system=tax_system,
        bank_kwargs=bank_kwargs,
        insurance_kwargs=insurance_kwargs,
        additional_expenses=data["additional_expenses"],
        has_employees=data["has_employees"],
    )
    result = calculate_net_profit(
        sale_price=required_sale,
        purchase_amount=data["purchase_amount"],
        tax_system=tax_system,
        bank_kwargs=bank_kwargs,
        insurance_kwargs=insurance_kwargs,
        additional_expenses=data["additional_expenses"],
        has_employees=data["has_employees"],
    )
    breakeven = calculate_breakeven(
        purchase_amount=data["purchase_amount"],
        tax_system=tax_system,
        bank_kwargs=bank_kwargs,
        insurance_kwargs=insurance_kwargs,
        additional_expenses=data["additional_expenses"],
        has_employees=data["has_employees"],
    )
    recommendations = generate_recommendations(result, tax_system)

    # Добавляем детали прочих расходов прямо в result для шаблона
    result["expense_shipping"] = data.get("expense_shipping") or Decimal("0")
    result["expense_guarantee"] = data.get("expense_guarantee") or Decimal("0")
    result["expense_etp"] = data.get("expense_etp") or Decimal("0")
    result["expense_other"] = data.get("expense_other") or Decimal("0")
    result["expense_other_label"] = data.get("expense_other_label") or "Прочее"

    # Сравнение УСН 6% vs 15% (только для этих двух систем)
    tax_comparison = None
    if tax_system in ("usn6", "usn15"):
        tax_comparison = compare_tax_systems(
            sale_price=required_sale,
            purchase_amount=data["purchase_amount"],
            additional_expenses=data["additional_expenses"],
            bank_kwargs=bank_kwargs,
            insurance_kwargs=insurance_kwargs,
            has_employees=data["has_employees"],
            current_tax_system=tax_system,
            expected_monthly_revenue=data.get("expected_monthly_revenue", Decimal("0")),
        )

    context = {
        "form": form,
        "result": result,
        "breakeven": breakeven,
        "required_sale": required_sale,
        "desired_profit": data["desired_profit"],
        "recommendations": recommendations,
        "tariff": tariff,
        "tax_system_label": dict(form.fields["tax_system"].choices)[tax_system],
        "tax_comparison": tax_comparison,
    }
    if request.headers.get("HX-Request"):
        return render(request, "calculator/partials/result.html", context)
    return render(request, "calculator/index.html", context)


# ─────────────────────────────────────────────────────
# КП поставщиков (единая страница)
# ─────────────────────────────────────────────────────

def offers_list(request: HttpRequest) -> HttpResponse:
    """
    Страница всех КП поставщиков.
    GET  ?req=<pk> — список КП + форма с предзаполненной потребностью.
    POST           — HTMX-добавление нового КП.
    """
    selected_req = None

    if request.method == "POST":
        form = SupplierOfferForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get("HX-Request"):
                requirements = Requirement.objects.prefetch_related("offers").all()
                return render(request, "calculator/partials/all_offers.html", {
                    "requirements": requirements,
                })
            return redirect("calculator:offers_list")
        if request.headers.get("HX-Request"):
            resp = render(request, "calculator/partials/req_form_errors.html",
                          {"form": form}, status=422)
            resp["HX-Retarget"] = "#offer-form-errors"
            resp["HX-Reswap"] = "innerHTML"
            return resp
    else:
        req_pk = request.GET.get("req")
        if req_pk:
            selected_req = Requirement.objects.filter(pk=req_pk).first()
        initial = {"requirement": selected_req} if selected_req else {}
        form = SupplierOfferForm(initial=initial)

    requirements = Requirement.objects.prefetch_related("offers").all()
    return render(request, "calculator/offers.html", {
        "form": form,
        "requirements": requirements,
        "selected_req": selected_req,
    })


# ─────────────────────────────────────────────────────
# Тарифы банков
# ─────────────────────────────────────────────────────

def tariffs(request: HttpRequest) -> HttpResponse:
    return render(request, "calculator/tariffs.html", {
        "tariffs": BankTariff.objects.all().order_by("bank", "name"),
        "tax_settings": TaxSettings.objects.order_by("-year"),
    })


@require_http_methods(["POST"])
def tariff_toggle_default(request: HttpRequest, pk: int) -> HttpResponse:
    tariff = get_object_or_404(BankTariff, pk=pk)
    BankTariff.objects.filter(is_default=True).update(is_default=False)
    tariff.is_default = True
    tariff.save(update_fields=["is_default"])
    messages.success(request, f"Тариф «{tariff}» установлен по умолчанию.")
    return redirect("calculator:tariffs")


# ─────────────────────────────────────────────────────
# Потребности и сравнение поставщиков (новая система)
# ─────────────────────────────────────────────────────

def requirements_list(request: HttpRequest) -> HttpResponse:
    """
    GET  — список потребностей + форма добавления.
    POST — HTMX-добавление новой потребности.
    """
    if request.method == "POST":
        form = RequirementForm(request.POST)
        if form.is_valid():
            req = form.save()
            if request.headers.get("HX-Request"):
                return render(request, "calculator/partials/requirement_row.html", {"req": req})
            return redirect("calculator:requirements")
        if request.headers.get("HX-Request"):
            resp = render(request, "calculator/partials/req_form_errors.html", {"form": form}, status=422)
            resp["HX-Retarget"] = "#req-form-errors"
            resp["HX-Reswap"] = "innerHTML"
            return resp
    else:
        form = RequirementForm()

    requirements = Requirement.objects.prefetch_related("offers").all()
    return render(request, "calculator/requirements.html", {
        "form": form,
        "requirements": requirements,
    })


@require_http_methods(["POST"])
def requirement_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX-удаление потребности вместе с её КП."""
    req = get_object_or_404(Requirement, pk=pk)
    req.delete()
    return HttpResponse("")  # HTMX удаляет строку через hx-target="closest tr" hx-swap="outerHTML"


def all_offers_partial(request: HttpRequest) -> HttpResponse:
    """HTMX: возвращает весь список КП (для кнопки «Отмена» в форме редактирования)."""
    requirements = Requirement.objects.prefetch_related("offers").all()
    return render(request, "calculator/partials/all_offers.html", {
        "requirements": requirements,
    })


def offer_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """
    GET  — возвращает строку с inline-формой редактирования.
    POST — сохраняет изменения, возвращает обновлённый список всех КП.
    """
    offer = get_object_or_404(SupplierOffer, pk=pk)

    if request.method == "POST":
        form = SupplierOfferEditForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            requirements = Requirement.objects.prefetch_related("offers").all()
            return render(request, "calculator/partials/all_offers.html", {
                "requirements": requirements,
            })
        # Ошибки — возвращаем форму редактирования с ошибками обратно в ту же строку
        return render(request, "calculator/partials/offer_edit_row.html", {
            "offer": offer,
            "form": form,
        })

    # GET — показываем форму редактирования
    form = SupplierOfferEditForm(instance=offer)
    return render(request, "calculator/partials/offer_edit_row.html", {
        "offer": offer,
        "form": form,
    })


def search_requirements(request: HttpRequest) -> HttpResponse:
    """HTMX-автокомплит: ищет потребности по имени. При пустом q — все потребности."""
    q = request.GET.get("q", "").strip()
    if q:
        results = Requirement.objects.filter(name__icontains=q)[:15]
    else:
        results = Requirement.objects.all()[:15]
    return render(request, "calculator/partials/requirement_search_results.html", {
        "results": results,
        "q": q,
    })


# ─────────────────────────────────────────────────────
# Поставки
# ─────────────────────────────────────────────────────

def delivery_list(request: HttpRequest) -> HttpResponse:
    """Список всех поставок."""
    deliveries = Delivery.objects.prefetch_related(
        "items__requirement", "items__selected_offer"
    ).all()
    return render(request, "calculator/deliveries.html", {"deliveries": deliveries})


@require_http_methods(["POST"])
def delivery_create(request: HttpRequest) -> HttpResponse:
    """Создание поставки из выбранных потребностей."""
    from datetime import date
    name = request.POST.get("delivery_name", "").strip()
    if not name:
        name = f"Поставка от {date.today().strftime('%d.%m.%Y')}"
    req_ids = request.POST.getlist("req_ids")
    if not req_ids:
        messages.warning(request, "Выберите хотя бы одну потребность.")
        return redirect("calculator:requirements")
    delivery = Delivery.objects.create(name=name)
    for req in Requirement.objects.filter(pk__in=req_ids):
        DeliveryItem.objects.get_or_create(delivery=delivery, requirement=req)
    return redirect("calculator:delivery_detail", pk=delivery.pk)


def delivery_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Страница поставки с таблицей позиций и встроенным калькулятором."""
    delivery = get_object_or_404(
        Delivery.objects.prefetch_related(
            "items__requirement__offers",
            "items__selected_offer",
        ),
        pk=pk,
    )
    app_settings = AppSettings.get()
    total_purchase = delivery.total_purchase

    default_tariff = (
        BankTariff.objects.filter(is_default=True, is_active=True).first()
        or BankTariff.objects.filter(is_active=True).first()
    )
    initial = {
        "purchase_amount": total_purchase,
        "expected_monthly_revenue": app_settings.expected_monthly_revenue,
        "desired_profit": Decimal("0"),
    }
    if default_tariff:
        initial["tariff"] = default_tariff

    form = CalculatorForm(initial=initial)
    return render(request, "calculator/delivery_detail.html", {
        "delivery": delivery,
        "form": form,
        "app_settings": app_settings,
        "total_purchase": total_purchase,
    })


@require_http_methods(["POST"])
def delivery_set_offer(request: HttpRequest, item_pk: int) -> HttpResponse:
    """HTMX: сменить КП для позиции поставки, вернуть обновлённую таблицу."""
    item = get_object_or_404(
        DeliveryItem.objects.select_related("delivery", "requirement"),
        pk=item_pk,
    )
    offer_pk = request.POST.get("offer_pk")
    if offer_pk:
        try:
            item.selected_offer = SupplierOffer.objects.get(
                pk=int(offer_pk), requirement=item.requirement
            )
        except (SupplierOffer.DoesNotExist, ValueError):
            item.selected_offer = None
    else:
        item.selected_offer = None
    item.save(update_fields=["selected_offer"])

    delivery = item.delivery
    items = delivery.items.select_related(
        "requirement", "selected_offer"
    ).prefetch_related("requirement__offers").all()

    return render(request, "calculator/partials/delivery_items.html", {
        "delivery": delivery,
        "items": items,
        "new_total": delivery.total_purchase,
    })


@require_http_methods(["POST"])
def delivery_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Удаление поставки."""
    delivery = get_object_or_404(Delivery, pk=pk)
    name = delivery.name
    delivery.delete()
    messages.success(request, f"Поставка «{name}» удалена.")
    return redirect("calculator:delivery_list")


@require_http_methods(["POST"])
def supplier_offer_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX-удаление КП поставщика."""
    offer = get_object_or_404(SupplierOffer, pk=pk)
    offer.delete()
    requirements = Requirement.objects.prefetch_related("offers").all()
    return render(request, "calculator/partials/all_offers.html", {
        "requirements": requirements,
    })
