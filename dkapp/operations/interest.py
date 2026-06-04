from datetime import date, datetime
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class InterestDataRow:
    date: str
    label: str
    amount: Decimal
    interest_rate: Decimal
    days_left_in_year: int
    interest: Decimal


class InterestProcessor:
    def __init__(self, contract, year):
        self.year = year
        self.start_date = date(self.year, 1, 1)
        self.end_date = date(self.year, 12, 31)
        self.contract = contract
        self.calculation_rows, self.auto_rows = self.calculate_rows()

    @property
    def value(self):
        r = sum([row.interest for row in self.calculation_rows]).quantize(Decimal('0.01'))
        return Decimal(0) if r == 0 else r

    @property
    def balance(self):
        r = sum([row.interest + row.amount for row in self.calculation_rows]).quantize(Decimal('0.01'))
        return Decimal(0) if r == 0 else r

    def calculate_rows(self):
        interest_rate, interest_type = self.contract.interest_rate_on(self.start_date)
        prev_interest_row = self._prev_interest_row()
        if prev_interest_row:
            interest_rows = [self._saldo_row(), prev_interest_row]
        else:
            interest_rows = [self._saldo_row()]

        contract_changes = self.contract.versions_in(self.year)
        if contract_changes:
            old_interest_rate = interest_rows[0].interest_rate
            old_prev_interest_rate = 0.0
            if prev_interest_row:
                old_prev_interest_rate = prev_interest_row.interest_rate
            for contract_change in contract_changes:
                if contract_change.id == self.contract.first_version.id:
                    continue
                if contract_change.start == self.start_date:
                    continue
                if old_interest_rate == contract_change.interest_rate:
                    continue

                interest_rows.extend(self._contract_change_rows(contract_change, old_interest_rate))
                if prev_interest_row:
                    interest_rows.extend(self._contract_change_prev_rows(contract_change, old_prev_interest_rate))
                    old_prev_interest_rate = contract_change.interest_rate if contract_change.interest_type.startswith(
                        'mit Zinseszins') else 0
                old_interest_rate = contract_change.interest_rate

        amount = self._saldo_row().amount
        accounting_entries = self.contract.accounting_entries_in(self.year)
        for entry in accounting_entries:
            interest_rows.append(self._accounting_row(entry, amount))
            if not entry.interest_relevant:
                amount += entry.amount

        auto_rows = []
        if interest_type.startswith('direkte Auszahlung'):
            r = self._payout_row(interest_rows)
            interest_rows.append(r)
            auto_rows.append(r)

        if self.contract.terminated_at and self.contract.terminated_at.year == self.year:
            r = self._contract_terminate_row(interest_rows, self.contract.terminated_at)
            interest_rows.append(r)
            auto_rows.append(r)

        return interest_rows, auto_rows

    def _saldo_row(self):
        start_balance = self.contract.balance_on(self.start_date)
        interest_rate, interest_type = self.contract.interest_rate_on(self.start_date)
        interest_for_year = (start_balance * interest_rate).quantize(Decimal('0.01'))

        return InterestDataRow(
            date=f"31. Dezember {self.start_date.year - 1}",
            label=f"Übertrag Darlehnsumme",
            amount=start_balance,
            interest_rate=interest_rate,
            days_left_in_year=360,
            interest=interest_for_year,
        )

    def _prev_interest_row(self):

        prev_interest = self.contract.prev_interest(self.start_date)
        if prev_interest is None or prev_interest == 0:
            return None

        interest_rate, interest_type = self.contract.interest_rate_on(self.start_date)
        if interest_type.startswith('direkte Auszahlung'):
            return None
        interest_for_year = (prev_interest * interest_rate).quantize(Decimal('0.01'))
        ci = interest_type.startswith('mit Zinseszins')

        return InterestDataRow(
            date=f"31. Dezember {self.start_date.year - 1}",
            label=f"Übertrag bisheriger angesparter Zinsen",
            amount=prev_interest,
            interest_rate=interest_rate if ci else Decimal(0),
            days_left_in_year=360,
            interest=interest_for_year if ci else Decimal(0),
        )

    def _accounting_row(self, accounting_entry, amount):
        days_left, fraction_year = self._days_fraction_360(accounting_entry.date)
        interest_rate, interest_type = self.contract.interest_rate_on(accounting_entry.date)
        calc_amount = accounting_entry.amount
        if interest_type.startswith("ohne Zinseszins"):
            calc_amount = max(calc_amount, -amount)
        interest = (calc_amount * Decimal(fraction_year) * interest_rate).quantize(Decimal('0.01'))
        return InterestDataRow(
            date=accounting_entry.date.strftime("%-d. %B %Y"),
            label=accounting_entry.comment if accounting_entry.comment else "Einzahlung" if accounting_entry.amount > 0 else "Auszahlung",
            amount=accounting_entry.amount,
            interest_rate=interest_rate,
            days_left_in_year=days_left,
            interest=Decimal(0) if interest == 0 else interest,
        )

    def _contract_change_rows(self, contract_version, old_interest_rate):
        change_balance = self.contract.balance_on(contract_version.start)
        days_left, fraction_year = self._days_fraction_360(contract_version.start)
        interest_before = (-change_balance * fraction_year * old_interest_rate).quantize(Decimal('0.01'))
        interest_after = (change_balance * fraction_year * contract_version.interest_rate).quantize(Decimal('0.01'))
        return [
            InterestDataRow(
                date=contract_version.start.strftime("%-d. %B %Y"),
                label="Vertragsänderung",
                amount=-change_balance,
                interest_rate=old_interest_rate,
                days_left_in_year=days_left,
                interest=interest_before,
            ),
            InterestDataRow(
                date=contract_version.start.strftime("%-d. %B %Y"),
                label="Vertragsänderung",
                amount=change_balance,
                interest_rate=contract_version.interest_rate,
                days_left_in_year=days_left,
                interest=interest_after
            )
        ]

    def _contract_change_prev_rows(self, contract_version, old_interest_rate):
        days_left, fraction_year = self._days_fraction_360(contract_version.start)
        prev_interest = self.contract.prev_interest(self.start_date)

        interest_before = (-prev_interest * fraction_year * old_interest_rate).quantize(Decimal('0.01'))
        ci = contract_version.interest_type.startswith('mit Zinseszins')
        interest_after = (prev_interest * fraction_year * contract_version.interest_rate).quantize(Decimal('0.01')) if ci else Decimal(0)

        return [
            InterestDataRow(
                date=contract_version.start.strftime("%-d. %B %Y"),
                label="Änderung Vorjahreszins",
                amount=-prev_interest,
                interest_rate=old_interest_rate,
                days_left_in_year=days_left,
                interest=interest_before,
            ),
            InterestDataRow(
                date=contract_version.start.strftime("%-d. %B %Y"),
                label="Änderung Vorjahreszins",
                amount=prev_interest,
                interest_rate=contract_version.interest_rate if ci else Decimal(0),
                days_left_in_year=days_left,
                interest=interest_after,
            )]

    def _payout_row(self, interest_rows):
        sum_interest = sum([i.interest for i in interest_rows])
        return InterestDataRow(
            date=f"31. Dezember {self.start_date.year}",
            label=f"Ausbuchung der Zinsen für {self.start_date.year}",
            amount=-sum_interest.quantize(Decimal('0.01')),
            interest_rate=Decimal(0),
            days_left_in_year=0,
            interest=Decimal(0),
        )

    def _contract_terminate_row(self, interest_rows, terminated_at):
        days_left, fraction_year = self._days_fraction_360(terminated_at)
        rest_balance = Decimal(0)
        rest_interest = Decimal(0)

        for i in interest_rows:
            rest_balance += i.amount
            if i.days_left_in_year > 0:
                rest_balance += Decimal(i.days_left_in_year - days_left) * i.interest / Decimal(i.days_left_in_year)
                rest_interest += Decimal(days_left) * i.interest / Decimal(i.days_left_in_year)

        return InterestDataRow(
            date=terminated_at.strftime("%-d. %B %Y"),
            label="Vertragsende",
            amount=-rest_balance.quantize(Decimal('0.01')),
            interest_rate=Decimal(0),
            days_left_in_year=days_left,
            interest=-rest_interest.quantize(Decimal('0.01')),
        )

    def _days_fraction_360(self, end_date):
        days_left = days360_eu(end_date, self.end_date)
        fraction = Decimal(days_left) / Decimal(360)
        return days_left, fraction


def days360_eu(start_date, end_date):
    start_day = start_date.day
    start_month = start_date.month
    start_year = start_date.year
    end_day = end_date.day
    end_month = end_date.month
    end_year = end_date.year

    if start_day == 31:
        start_day = 30

    if end_day == 31:
        end_day = 30

    return (end_year - start_year) * 360 + (end_month - start_month) * 30 + (end_day - start_day)
