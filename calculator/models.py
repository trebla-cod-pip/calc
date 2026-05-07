"""
Модели для хранения тарифов банков, настроек налогообложения
и коммерческих предложений поставщиков.
"""
from django.db import models


class BankTariff(models.Model):
    """Тариф банка для расчёта комиссий ИП."""

    BANK_CHOICES = [
        ("tbank", "Т-Банк"),
        ("sberbank", "Сбербанк"),
        ("alfa", "Альфа-Банк"),
        ("other", "Другой банк"),
    ]

    bank = models.CharField("Банк", max_length=20, choices=BANK_CHOICES, default="tbank")
    name = models.CharField("Название тарифа", max_length=100)
    is_active = models.BooleanField("Активный", default=True)
    is_default = models.BooleanField(
        "По умолчанию",
        default=False,
        help_text="Только один тариф может быть тарифом по умолчанию",
    )

    # --- Обслуживание счёта ---
    maintenance_fee = models.DecimalField(
        "Обслуживание счёта, ₽/мес",
        max_digits=10,
        decimal_places=2,
        default=490,
    )
    maintenance_free_condition = models.TextField(
        "Условие бесплатного обслуживания",
        blank=True,
        default="Нет операций ИЛИ покупки по бизнес-карте от 150 000 ₽/мес",
    )

    # --- Исходящие платежи поставщику ---
    outgoing_same_bank_fee = models.DecimalField(
        "Перевод поставщику в том же банке, ₽",
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    outgoing_other_bank_fee = models.DecimalField(
        "Перевод поставщику в другой банк, ₽",
        max_digits=10,
        decimal_places=2,
        default=49,
    )

    # --- Вывод на личную карту (JSON-конфигурация прогрессивной шкалы) ---
    withdrawal_config = models.JSONField(
        "Настройки вывода на карту (JSON)",
        default=dict,
        help_text="Прогрессивная шкала комиссий за вывод. up_to=null означает «без верхней границы».",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Банковский тариф"
        verbose_name_plural = "Банковские тарифы"
        ordering = ["bank", "name"]

    def __str__(self) -> str:
        return f"{self.get_bank_display()} — {self.name}"


class TaxSettings(models.Model):
    """Ежегодные настройки налогов и страховых взносов для ИП."""

    year = models.IntegerField("Год", unique=True, default=2026)

    fixed_insurance_annual = models.DecimalField(
        "Фиксированные взносы ИП за год, ₽",
        max_digits=12,
        decimal_places=2,
        default=49500,
        help_text="Обязательные взносы на ОПС + ОМС без сотрудников. 2026 г. — 49 500 ₽.",
    )

    additional_insurance_threshold = models.DecimalField(
        "Порог дохода для 1%, ₽/год",
        max_digits=12,
        decimal_places=2,
        default=300000,
    )

    additional_insurance_rate = models.DecimalField(
        "Ставка дополнительного взноса, %",
        max_digits=5,
        decimal_places=2,
        default=1,
    )

    class Meta:
        verbose_name = "Настройки налогов"
        verbose_name_plural = "Настройки налогов"
        ordering = ["-year"]

    def __str__(self) -> str:
        return f"Настройки ИП на {self.year} год (взносы: {self.fixed_insurance_annual} ₽)"


class Requirement(models.Model):
    """Потребность в закупке — что нужно купить."""

    name = models.CharField("Наименование товара", max_length=200)
    short_name = models.CharField(
        "Сокращённое наименование", max_length=60, blank=True,
        help_text="Краткое название для таблиц и списков (до 60 символов)",
    )
    quantity = models.PositiveIntegerField("Количество", default=1)
    unit = models.CharField(
        "Единица измерения", max_length=20, default="шт.",
        help_text="шт., кг, м, л, уп. и т.д.",
    )
    description = models.TextField("Описание / требования", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Потребность"
        verbose_name_plural = "Потребности"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        display = self.short_name or self.name
        return f"{display} — {self.quantity} {self.unit}"

    @property
    def best_offer(self) -> "SupplierOffer | None":
        return self.offers.order_by("total_price").first()


class SupplierOffer(models.Model):
    """Коммерческое предложение поставщика на конкретную потребность."""

    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name="offers",
        verbose_name="Потребность",
    )
    supplier_name = models.CharField("Поставщик", max_length=200)
    price_per_unit = models.DecimalField(
        "Цена за единицу, ₽", max_digits=14, decimal_places=2
    )
    total_price = models.DecimalField(
        "Итоговая сумма, ₽", max_digits=14, decimal_places=2,
        editable=False, default=0,
    )
    delivery_days = models.PositiveIntegerField(
        "Срок доставки, дней", blank=True, null=True
    )
    link = models.URLField("Ссылка на товар / КП", blank=True)
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "КП поставщика"
        verbose_name_plural = "КП поставщиков"
        ordering = ["total_price"]

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.total_price = self.price_per_unit * Decimal(self.requirement.quantity)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.supplier_name} → {self.requirement.name}: {self.total_price} ₽"


class Delivery(models.Model):
    """Поставка — набор потребностей для совместного расчёта."""
    name = models.CharField("Название поставки", max_length=200)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Поставка"
        verbose_name_plural = "Поставки"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def total_purchase(self):
        from decimal import Decimal
        total = Decimal("0")
        for item in self.items.all():
            offer = item.selected_offer or item.requirement.best_offer
            if offer:
                total += offer.total_price
        return total

    @property
    def has_missing_offers(self):
        for item in self.items.all():
            if not (item.selected_offer or item.requirement.best_offer):
                return True
        return False


class DeliveryItem(models.Model):
    """Позиция в поставке."""
    delivery = models.ForeignKey(
        Delivery, on_delete=models.CASCADE, related_name="items",
        verbose_name="Поставка",
    )
    requirement = models.ForeignKey(
        Requirement, on_delete=models.PROTECT, related_name="delivery_items",
        verbose_name="Потребность",
    )
    selected_offer = models.ForeignKey(
        SupplierOffer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="delivery_items", verbose_name="Выбранное КП",
    )

    class Meta:
        verbose_name = "Позиция поставки"
        verbose_name_plural = "Позиции поставки"
        unique_together = [("delivery", "requirement")]
        ordering = ["requirement__name"]

    def __str__(self) -> str:
        return str(self.requirement)

    @property
    def active_offer(self):
        return self.selected_offer or self.requirement.best_offer

    @property
    def active_total(self):
        offer = self.active_offer
        return offer.total_price if offer else None


class AppSettings(models.Model):
    """
    Singleton-модель для хранения пользовательских настроек приложения.
    Всегда одна запись (pk=1). Используйте AppSettings.get() для доступа.
    """
    expected_monthly_revenue = models.DecimalField(
        "Ожидаемая выручка в месяц, ₽",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text=(
            "Типичный ежемесячный оборот ИП. "
            "Используется для пропорционального распределения "
            "фиксированных взносов и обслуживания счёта по сделкам."
        ),
    )

    class Meta:
        verbose_name = "Настройки приложения"
        verbose_name_plural = "Настройки приложения"

    def __str__(self) -> str:
        return f"Настройки (выручка: {self.expected_monthly_revenue} ₽/мес)"

    @classmethod
    def get(cls) -> "AppSettings":
        """Возвращает единственную запись, создаёт при необходимости."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class VendorOffer(models.Model):
    """
    Коммерческое предложение (КП) от поставщика.

    Хранит данные для сравнения предложений при поиске товара:
    цену, доставку, сроки и ссылку на КП.
    """

    # Название поставщика / источника КП
    name = models.CharField(
        "Поставщик",
        max_length=200,
        help_text="Название компании или площадки (Wildberries, ООО Ромашка и т.д.)",
    )

    # Цена за единицу товара
    unit_price = models.DecimalField(
        "Цена за единицу, ₽",
        max_digits=14,
        decimal_places=2,
    )

    # Стоимость доставки всего заказа (не за единицу)
    shipping_cost = models.DecimalField(
        "Стоимость доставки, ₽",
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Срок поставки
    delivery_days = models.PositiveIntegerField(
        "Срок поставки, дней",
        default=0,
    )

    # Ссылка на файл КП или страницу товара
    document_url = models.URLField(
        "Ссылка на КП / товар",
        blank=True,
        help_text="URL файла КП, страницы товара или облачного документа",
    )

    # Произвольный комментарий
    comment = models.TextField(
        "Комментарий",
        blank=True,
        help_text="Особые условия, минимальная партия, качество и т.д.",
    )

    created_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "КП поставщика"
        verbose_name_plural = "КП поставщиков"
        ordering = ["unit_price", "shipping_cost"]

    def __str__(self) -> str:
        return f"{self.name} — {self.unit_price} ₽/шт"

    def total_cost(self, quantity: int = 1) -> "Decimal":
        """Итоговая стоимость заказа: цена × кол-во + доставка."""
        from decimal import Decimal
        return self.unit_price * Decimal(quantity) + self.shipping_cost
