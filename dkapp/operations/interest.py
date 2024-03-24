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
    interest: float


class InterestProcessor:
    def __init__(self, contract, year):
        self.year = year
        self.start_date = date(self.year, 1, 1)
        self.end_date = date(self.year, 12, 31)
        self.contract = contract
        self.calculation_rows,self.auto_rows = self.calculate_rows()

    @property
    def value(self):
        return sum([float(row.interest) for row in self.calculation_rows])

    @property
    def balance(self):
        return sum([Decimal(row.interest) + row.amount for row in self.calculation_rows])

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

        accounting_entries = self.contract.accounting_entries_in(self.year)
        for entry in accounting_entries:
            interest_rows.append(self._accounting_row(entry))

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
        interest_for_year = round(start_balance * interest_rate, 2)

        return InterestDataRow(
            date=f"Übertrag aus {self.start_date.year - 1}",
            label="Saldo",
            amount=start_balance,
            interest_rate=interest_rate,
            days_left_in_year=360,
            interest=interest_for_year,
        )

    def _prev_interest_row(self):

        prev_interest = self.contract.prev_interest(self.start_date)
        if prev_interest is None:
            return None

        interest_rate, interest_type = self.contract.interest_rate_on(self.start_date)
        if interest_type.startswith('direkte Auszahlung'):
            return None
        interest_for_year = round(prev_interest * interest_rate, 2)
        ci = interest_type.startswith('mit Zinseszins')

        return InterestDataRow(
            date=f"Übertrag aus {self.start_date.year - 1}",
            label="Zinsen aus den Vorjahren",
            amount=prev_interest,
            interest_rate=interest_rate if ci else 0,
            days_left_in_year=360,
            interest=interest_for_year if ci else 0,
        )

    def _accounting_row(self, accounting_entry):
        days_left, fraction_year = self._days_fraction_360(accounting_entry.date)

        interest_rate, interest_type = self.contract.interest_rate_on(accounting_entry.date)
        interest = round(accounting_entry.amount * fraction_year * interest_rate, 2)
        # if interest<0:
        #     interest = interest/(1+(1-fraction_year)*interest_rate)
        # interest -= interest*(1-fraction_year) * interest_rate
        return InterestDataRow(
            date=accounting_entry.date,
            label=accounting_entry.comment if accounting_entry.comment else "Einzahlung" if accounting_entry.amount > 0 else "Auszahlung",
            amount=accounting_entry.amount,
            interest_rate=interest_rate,
            days_left_in_year=days_left,
            interest=Decimal(0) if interest == 0 else interest,
        )

    def _contract_change_rows(self, contract_version, old_interest_rate):
        change_balance = self.contract.balance_on(contract_version.start)
        days_left, fraction_year = self._days_fraction_360(contract_version.start)
        interest_before = round(-change_balance * fraction_year * old_interest_rate, 2)
        interest_after = round(change_balance * fraction_year * contract_version.interest_rate, 2)
        return [
            InterestDataRow(
                date=contract_version.start,
                label="Vertragsänderung",
                amount=-change_balance,
                interest_rate=old_interest_rate,
                days_left_in_year=days_left,
                interest=interest_before,
            ),
            InterestDataRow(
                date=contract_version.start,
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

        return [
            InterestDataRow(
                date=contract_version.start,
                label="Änderung Vorjahreszins",
                amount=-prev_interest,
                interest_rate=old_interest_rate,
                days_left_in_year=days_left,
                interest=round(-prev_interest * fraction_year * old_interest_rate, 2),
            ),
            InterestDataRow(
                date=contract_version.start,
                label="Änderung Vorjahreszins",
                amount=prev_interest,
                interest_rate=contract_version.interest_rate if contract_version.interest_type.startswith(
                    'mit Zinseszins') else 0,
                days_left_in_year=days_left,
                interest=round(prev_interest * fraction_year * contract_version.interest_rate,
                               2) if contract_version.interest_type.startswith('mit Zinseszins') else 0,
            )]

    def _payout_row(self, interest_rows):
        sum_interest = 0
        for i in interest_rows:
            sum_interest += i.interest
        return InterestDataRow(
            date="",
            label="Zinsauszahlung",
            amount=Decimal(0) if round(sum_interest, 2) == 0 else Decimal(-sum_interest),
            interest_rate=Decimal(0),
            days_left_in_year=0,
            interest=0,
        )

    def _contract_terminate_row(self, interest_rows, terminated_at):
        days_left, fraction_year = self._days_fraction_360(terminated_at)
        rest_balance = 0
        rest_interest = 0

        for i in interest_rows:
            rest_balance += float(i.amount)
            if i.days_left_in_year > 0:
                rest_balance += (i.days_left_in_year - days_left) * float(i.interest) / i.days_left_in_year
                rest_interest += days_left * float(i.interest) / i.days_left_in_year

        return InterestDataRow(
                date=terminated_at,
                label="Vertragsende",
                amount=Decimal(0) if round(rest_balance, 2) == 0 else Decimal(-rest_balance),
                interest_rate=Decimal(0),
                days_left_in_year=days_left,
                interest=Decimal(0) if round(rest_interest, 2) == 0 else -rest_interest,
            )

    def _days_fraction_360(self, end_date):
        days_left = days360_eu(end_date, self.end_date)
        # days_left += 1  # 2n40-Hack
        fraction = Decimal(days_left / 360)
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
