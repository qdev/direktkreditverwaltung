import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from datetime import date
from dateutil.relativedelta import relativedelta

from django.utils import timezone
from django.db import models

from dkapp.operations.interest import days360_eu

# Get an instance of a logger
logger = logging.getLogger(__name__)


class Contact(models.Model):
    number = models.IntegerField()
    last_name = models.CharField(max_length=200)
    first_name = models.CharField(max_length=200)
    address = models.CharField(max_length=200, blank=True)
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

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


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
    terminated_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.contact.number:04d}-{self.number:02d} ({self.contact})"

    @property
    def last_version(self):
        return self.contractversion_set.order_by('start').last()

    @property
    def first_version(self):
        return self.contractversion_set.order_by('start').first()

    @property
    def balance(self):
        return self.balance_on(timezone.now()) + self.prev_interest(timezone.now())

    def balance_on(self, date):
        """Account balance for given date"""
        return self.accountingentry_set.filter(
            date__lt=date
        ).aggregate(
            models.Sum('amount')
        )['amount__sum'] or Decimal('0')

    def infla_limit(self, rate, year):
        infla_dict = {
            2013: 0.0200,
            2014: 0.0090,
            2015: 0.0024,
            2016: 0.0049,
            2017: 0.0177,
            2018: 0.0190,
            2019: 0.0140,
            2020: 0.0047,
            2021: 0.0310,
            2022: 0.0790,
            2023: 0.0500,
        }
        return float(min(rate, infla_dict[year]) if year in infla_dict else rate)

    def add_fraction(self, d1, d2, amount, pa, rate, compound_interest, inflalimit, fractions):
        date = d1
        for d in range(d1.year, d2.year):
            days = days360_eu(date, datetime(d, 12, 31))
            r = self.infla_limit(rate, d) if inflalimit else float(rate)
            fractions.append((days, amount, r))
            if compound_interest:
                amount += pa + amount * r * days / 360
                pa = 0
            date = datetime(d, 12, 31)
        days = days360_eu(date, d2)
        r = self.infla_limit(rate, d2.year) if inflalimit else float(rate)
        fractions.append((days, amount, r))
        pa += amount * r * days / 360
        return amount, pa

    def prev_interest(self, until):

        accountingentries = list(self.accountingentry_set.filter(date__lte=until).order_by('date'))
        contractversions = list(self.contractversion_set.filter(start__lte=until).order_by('start'))
        if not contractversions or contractversions[0].start.year > until.year:
            return None

        amount = 0.0
        pa = 0.0
        rate = float(contractversions[0].interest_rate)

        year = contractversions[0].start.year
        if accountingentries:
            year = min(year, accountingentries[0].date.year)
        date = datetime(year-1, 12, 31)
        fractions = []
        compound_interest = False
        inflalimit = False

        while accountingentries or contractversions:
            if contractversions and (not accountingentries or contractversions[0].start < accountingentries[0].date):
                amount, pa = self.add_fraction(date, contractversions[0].start, amount, pa, rate, compound_interest, inflalimit, fractions)
                compound_interest = contractversions[0].interest_type.startswith("mit Zinseszins")
                rate = contractversions[0].interest_rate
                inflalimit = contractversions[0].interest_type.endswith(", Inflationlimit")
                date = contractversions.pop(0).start
            else:
                amount, pa = self.add_fraction(date, accountingentries[0].date, amount, pa, rate, compound_interest, inflalimit, fractions)
                amount += float(accountingentries[0].amount)
                date = accountingentries.pop(0).date
        #self.add_fraction(date, until, amount, rate, compound_interest, inflalimit, fractions)
        # 2n40-Hack:
        self.add_fraction(date, until - timedelta(days=1), amount, pa, rate, compound_interest, inflalimit, fractions)

        print(fractions)
        print([x[0] * x[1] * float(x[2]) / 360 for x in fractions])
        return Decimal(sum([x[0] * x[1] * float(x[2]) / 360 for x in fractions]))

    def versions_in(self, year):
        return self.contractversion_set.filter(start__year=year).order_by('start')

    def version_at(self, reference_date: date):
        current_version = self.first_version
        sorted = self.contractversion_set.order_by('start').order_by('start')
        for version in sorted:
            if version.start > reference_date:
                return current_version
            current_version = version
        return current_version

    def interest_rate_on(self, date=None):
        versions = self.contractversion_set.order_by('-start')
        r = Decimal('0'), ""
        for version in versions:
            r = version.interest_rate, version.interest_type
            if version.start <= date:
                break
        return (Decimal(self.infla_limit(r[0], date.year)),r[1]) if r[1].endswith(", Inflationlimit") else r

    def accounting_entries_in(self, year):
        return self.accountingentry_set.filter(date__year=year).order_by('date')

    @property
    def expiring(self):
        return self.last_version.expiring

    def expiring_at(self, reference_date: date):
        return self.version_at(reference_date).expiring

    def remaining_years(self, reference_date: Optional[date] = None) -> float:
        if not reference_date:
            reference_date = date.today()
        return (self.expiring_at(reference_date) - reference_date).days/365

    @classmethod
    def total_sum(cls):
        contracts = cls.objects.all()
        return sum([contract.balance for contract in contracts])


class ContractVersion(models.Model):
    class Type(models.TextChoices):
        OHNE_ZZ = 'ohne Zinseszins'
        MIT_ZZ = 'mit Zinseszins'
        AUSZAHLEN = 'direkte Auszahlung'
        OHNE_ZZ_IL = 'ohne Zinseszins, Inflationlimit'
        MIT_ZZ_IL = 'mit Zinseszins, Inflationlimit'
        AUSZAHLEN_IL = 'direkte Auszahlung, Inflationlimit'

    start = models.DateField()
    duration_months = models.IntegerField(null=True, blank=True)
    cancellation_months = models.IntegerField(null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=4)
    interest_type = models.CharField(max_length=200, choices=Type.choices)
    version = models.IntegerField()
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Version {self.version} des Vertrags {self.contract}"

    @property
    def expiring(self):
        return self.start + relativedelta(months=self.duration_months or 0) + relativedelta(years=self.duration_years or 0)

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

    @classmethod
    def total_sum(cls):
        return cls.objects.aggregate(models.Sum('amount'))['amount__sum'] or 0
