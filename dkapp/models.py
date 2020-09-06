from dateutil.relativedelta import relativedelta

from django.utils import timezone
from django.db import models


class Contact(models.Model):
    last_name = models.CharField(max_length=200)
    first_name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    phone = models.CharField(max_length=200, blank=True)
    email = models.CharField(max_length=200, blank=True)
    iban = models.CharField(max_length=200, blank=True)
    bic = models.CharField(max_length=200, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    remark = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.last_name}, {self.first_name}"


class Contract(models.Model):
    class Category(models.TextChoices):
        PRIVAT = 'Privat'
        SYNDIKAT = 'Syndikat'
        DRITTE = 'Dritte'

    number = models.IntegerField()
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    comment = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=200, choices=Category.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Direktkreditvertrag {self.number} von {self.contact}"

    @property
    def balance(self, date=None):
        """Account balance for given date"""
        date = date or timezone.now()
        return self.accountingentry_set .filter(
            date__lte=date
        ).aggregate(
            models.Sum('amount')
        )['amount__sum'] or 0

    @property
    def last_version(self):
        return self.contractversion_set.order_by('start').last()

    @property
    def expiring(self):
        last_version = self.last_version
        return last_version.start + relativedelta(months=last_version.duration_months or 0) + relativedelta(years=last_version.duration_years or 0)


class ContractVersion(models.Model):
    start = models.DateField()
    duration_months = models.IntegerField(null=True, blank=True)
    duration_years = models.IntegerField(null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=4)
    version = models.IntegerField()
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Version {self.version} des Vertrags {self.contract}"


class AccountingEntry(models.Model):
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Buchung {self.id} vom {self.date.strftime('%d.%m.%Y')} in {self.contract}"

    @property
    def type(self):
        return "Einzahlung" if self.amount >= 0 else "Auszahlung"
