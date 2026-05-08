"""
Формы для калькулятора прибыли ИП и сравнения поставщиков.
"""
from decimal import Decimal
from django import forms

from .models import BankTariff, Deal, Requirement, SupplierOffer, VendorOffer

TAX_SYSTEM_CHOICES = [
    ("usn6", "УСН 6% (доходы)"),
    ("usn15", "УСН 15% (доходы − расходы)"),
    ("npd_individual", "НПД 4% (физлица)"),
    ("npd_legal", "НПД 6% (юрлица/ИП)"),
    ("osno", "ОСНО (НДФЛ + НДС)"),
]


class CalculatorForm(forms.Form):
    """Основная форма расчёта прибыли."""

    purchase_amount = forms.DecimalField(
        label="Сумма закупки, ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-input",
            "placeholder": "100 000",
            "step": "0.01",
            "min": "0",
        }),
        help_text="Сумма, которую вы платите поставщику за товар/услугу",
    )

    desired_profit = forms.DecimalField(
        label="Желаемый заработок (чистая прибыль), ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-input",
            "placeholder": "30 000",
            "step": "0.01",
            "min": "0",
        }),
        help_text="Сколько вы хотите получить «на руки» после всех налогов и комиссий",
    )

    tariff = forms.ModelChoiceField(
        label="Тариф банка",
        queryset=BankTariff.objects.filter(is_active=True),
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    supplier_in_same_bank = forms.BooleanField(
        label="Поставщик обслуживается в том же банке",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Перевод в тот же банк — 0 ₽. В другой банк — 49 ₽ (тариф «Простой»)",
    )

    maintenance_condition_met = forms.BooleanField(
        label="Условие бесплатного обслуживания выполнено",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Например, покупки по бизнес-карте от 150 000 ₽/мес",
    )

    withdrawal_amount = forms.DecimalField(
        label="Вывод на личную карту, ₽/мес",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input",
            "placeholder": "0",
            "step": "0.01",
            "min": "0",
        }),
        help_text="Сумма вывода со счёта ИП на личную карту Т-Банка за месяц",
    )

    withdrawal_operations = forms.IntegerField(
        label="Количество операций вывода в месяц",
        min_value=1,
        max_value=100,
        initial=1,
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input",
            "placeholder": "1",
            "min": "1",
            "max": "100",
        }),
        help_text="Количество отдельных переводов себе на карту за месяц",
    )

    tax_system = forms.ChoiceField(
        label="Система налогообложения",
        choices=TAX_SYSTEM_CHOICES,
        initial="usn6",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    has_employees = forms.BooleanField(
        label="Есть наёмные сотрудники",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        help_text="Влияет на вычет взносов при УСН 6%: без сотрудников — до 100%, с сотрудниками — до 50%",
    )

    expected_monthly_revenue = forms.DecimalField(
        label="Ожидаемая выручка в месяц, ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input",
            "placeholder": "0 — не учитывать",
            "step": "1000",
            "min": "0",
        }),
        help_text=(
            "Ваш типичный оборот в месяц. Если заполнено — фиксированные взносы "
            "(49 500 ₽/год) распределяются пропорционально этой сделке, "
            "а не закладываются полностью (4 125 ₽) в каждую."
        ),
    )

    # ── Прочие расходы (разбивка) ──────────────────────────────────────────
    expense_shipping = forms.DecimalField(
        label="Доставка, ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input expense-item",
            "placeholder": "0",
            "step": "0.01",
            "min": "0",
        }),
    )

    expense_guarantee = forms.DecimalField(
        label="Банковская гарантия, ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input expense-item",
            "placeholder": "0",
            "step": "0.01",
            "min": "0",
        }),
    )

    expense_etp = forms.DecimalField(
        label="Комиссия ЭТП / спецсчёт, ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input expense-item",
            "placeholder": "0",
            "step": "0.01",
            "min": "0",
        }),
    )

    expense_other_label = forms.CharField(
        label="Название статьи «Прочее»",
        max_length=100,
        initial="",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "Сертификация, упаковка…",
        }),
    )

    expense_other = forms.DecimalField(
        label="Прочее, ₽",
        min_value=Decimal("0"),
        max_digits=14,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-input expense-item",
            "placeholder": "0",
            "step": "0.01",
            "min": "0",
        }),
    )

    def clean_withdrawal_amount(self) -> Decimal:
        value = self.cleaned_data.get("withdrawal_amount")
        return value or Decimal("0")

    def clean_withdrawal_operations(self) -> int:
        value = self.cleaned_data.get("withdrawal_operations")
        return value or 1

    def clean_expected_monthly_revenue(self) -> Decimal:
        value = self.cleaned_data.get("expected_monthly_revenue")
        return value or Decimal("0")

    def clean(self) -> dict:
        super().clean()
        # Суммируем все статьи прочих расходов в одно поле для сервисов
        self.cleaned_data["additional_expenses"] = sum(
            self.cleaned_data.get(f, Decimal("0")) or Decimal("0")
            for f in ("expense_shipping", "expense_guarantee", "expense_etp", "expense_other")
        )
        return self.cleaned_data


class VendorOfferForm(forms.ModelForm):
    """Форма добавления КП поставщика."""

    class Meta:
        model = VendorOffer
        fields = ["name", "unit_price", "shipping_cost", "delivery_days", "document_url", "comment"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "ООО Ромашка / Wildberries / Alibaba",
                "autofocus": True,
            }),
            "unit_price": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "1 500.00",
                "step": "0.01",
                "min": "0",
            }),
            "shipping_cost": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "0",
                "step": "0.01",
                "min": "0",
            }),
            "delivery_days": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "7",
                "min": "0",
            }),
            "document_url": forms.URLInput(attrs={
                "class": "form-input",
                "placeholder": "https://...",
            }),
            "comment": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 2,
                "placeholder": "Минимальная партия 10 шт., возможна рассрочка...",
            }),
        }
        labels = {
            "name": "Поставщик",
            "unit_price": "Цена за единицу, ₽",
            "shipping_cost": "Стоимость доставки, ₽",
            "delivery_days": "Срок поставки, дней",
            "document_url": "Ссылка на КП / товар",
            "comment": "Комментарий",
        }


class RequirementForm(forms.ModelForm):
    """Форма создания потребности в закупке."""

    class Meta:
        model = Requirement
        fields = ["name", "short_name", "quantity", "unit", "description"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Офисные кресла / Ноутбуки Dell / Бумага А4",
                "autofocus": True,
            }),
            "short_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Кресла офисные / Ноутбуки / Бумага",
                "maxlength": "60",
            }),
            "quantity": forms.NumberInput(attrs={
                "class": "form-input",
                "min": "1",
                "placeholder": "10",
            }),
            "unit": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "шт.",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 2,
                "placeholder": "Требования к качеству, сроки, особые условия…",
            }),
        }
        labels = {
            "name": "Наименование товара",
            "short_name": "Сокращённое наименование",
            "quantity": "Количество",
            "unit": "Единица измерения",
            "description": "Описание / требования",
        }


class SupplierOfferForm(forms.ModelForm):
    """
    Форма добавления КП поставщика к потребности.
    Поле requirement реализовано через HTMX-автокомплит.
    """

    # Скрытое поле для хранения выбранного ID потребности
    requirement = forms.ModelChoiceField(
        queryset=Requirement.objects.all(),
        widget=forms.HiddenInput(),
        error_messages={"required": "Выберите потребность из списка"},
    )

    # Текстовый поиск — не является полем формы, только для UI
    requirement_search = forms.CharField(
        label="Потребность",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "Начните вводить название…",
            "autocomplete": "off",
            "hx-get": "",  # заполняется в шаблоне через тег url
            "hx-trigger": "keyup changed delay:300ms",
            "hx-target": "#req-search-results",
            "hx-swap": "innerHTML",
            "hx-vals": '{"q": ""}',  # перезаписывается через input name
        }),
    )

    class Meta:
        model = SupplierOffer
        fields = ["requirement", "supplier_name", "price_per_unit", "delivery_days", "link", "comment"]
        widgets = {
            "supplier_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "ООО Ромашка / Wildberries / Alibaba",
            }),
            "price_per_unit": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "1 500.00",
                "step": "0.01",
                "min": "0",
            }),
            "delivery_days": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "7",
                "min": "0",
            }),
            "link": forms.URLInput(attrs={
                "class": "form-input",
                "placeholder": "https://…",
            }),
            "comment": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 2,
                "placeholder": "Минимальная партия, условия оплаты…",
            }),
        }
        labels = {
            "supplier_name": "Поставщик",
            "price_per_unit": "Цена за единицу, ₽",
            "delivery_days": "Срок доставки, дней",
            "link": "Ссылка на КП / товар",
            "comment": "Комментарий",
        }


class DealForm(forms.ModelForm):
    """Форма сохранения / редактирования сделки."""

    # Название необязательно в форме — view подставляет дефолт из delivery.name
    title = forms.CharField(
        label="Название сделки",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-input", "placeholder": "Сделка по контракту №123",
        }),
    )

    class Meta:
        model = Deal
        fields = [
            "title", "client_name", "invoice_number", "status",
            "purchase_date", "delivery_date", "payment_date",
            "revenue", "cost_price", "tax_amount", "gross_tax",
            "bank_commission", "insurance_amount", "other_expenses",
            "tax_system", "comment",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input", "placeholder": "Сделка по контракту №123",
            }),
            "client_name": forms.TextInput(attrs={
                "class": "form-input", "placeholder": "ООО Заказчик / ИП Иванов",
            }),
            "invoice_number": forms.TextInput(attrs={
                "class": "form-input", "placeholder": "СЧ-001 / Договор №45",
            }),
            "status": forms.Select(attrs={"class": "form-select"}),
            "purchase_date":  forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "delivery_date":  forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "payment_date":   forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "revenue":           forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "cost_price":        forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "tax_amount":        forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "bank_commission":   forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "insurance_amount":  forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "other_expenses":    forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "gross_tax":         forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "0"}),
            "tax_system":        forms.HiddenInput(),
            "comment": forms.Textarea(attrs={"class": "form-input", "rows": 2, "placeholder": "Дополнительные заметки…"}),
        }
        labels = {
            "title": "Название сделки",
            "client_name": "Заказчик / клиент",
            "invoice_number": "Номер счёта / договора",
            "status": "Статус",
            "purchase_date": "Дата закупки",
            "delivery_date": "Дата поставки",
            "payment_date": "Дата оплаты клиентом",
            "revenue": "Выручка (цена продажи), ₽",
            "cost_price": "Себестоимость, ₽",
            "tax_amount": "Налог, ₽",
            "bank_commission": "Комиссия банка, ₽",
            "insurance_amount": "Страховые взносы, ₽",
            "other_expenses": "Прочие расходы, ₽",
            "comment": "Комментарий",
        }


class SupplierOfferEditForm(forms.ModelForm):
    """Форма редактирования КП (без смены потребности)."""

    class Meta:
        model = SupplierOffer
        fields = ["supplier_name", "price_per_unit", "delivery_days", "link", "comment"]
        widgets = {
            "supplier_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "ООО Ромашка / Wildberries / Alibaba",
                "autofocus": True,
            }),
            "price_per_unit": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "1 500.00",
                "step": "0.01",
                "min": "0",
            }),
            "delivery_days": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "7",
                "min": "0",
            }),
            "link": forms.URLInput(attrs={
                "class": "form-input",
                "placeholder": "https://…",
            }),
            "comment": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 2,
                "placeholder": "Минимальная партия, условия оплаты…",
            }),
        }
        labels = {
            "supplier_name": "Поставщик",
            "price_per_unit": "Цена/шт, ₽",
            "delivery_days": "Срок, дн.",
            "link": "Ссылка",
            "comment": "Комментарий",
        }
