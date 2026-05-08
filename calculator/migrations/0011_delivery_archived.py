from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calculator", "0010_add_deal_tax_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="delivery",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="В архиве"),
        ),
    ]
