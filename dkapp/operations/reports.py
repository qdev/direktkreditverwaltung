from datetime import datetime, date
from decimal import Decimal
from typing import List, Tuple
from dataclasses import dataclass
from dkapp.models import Contact, Contract, AccountingEntry
from django.db.models import Q
from dkapp.operations.interest import InterestProcessor, InterestDataRow


@dataclass
class FractionPerContract:
    contract: Contract
    balance: float
    fraction_credit: float
    interest_rate: float
    relative_interest_rate: float


class AverageInterestRateReport:
    def __init__(self, contracts, sum_credit):
        self.sum_credit = sum_credit
        self.per_contract_data = [
            FractionPerContract(
                contract=contract,
                balance=balance,
                fraction_credit=(fraction := balance / sum_credit),
                interest_rate=(interest_rate := contract.last_version.interest_rate),
                interest_type=(interest_type := contract.last_version.interest_type),
                relative_interest_rate=interest_rate * fraction,
            ) for contract in contracts if (balance := contract.balance) > 0
        ]
        self.avg_interest_rate = sum([data.relative_interest_rate for data in self.per_contract_data])

    @classmethod
    def create(cls):
        all_contracts = Contract.objects.order_by('number')
        assert AccountingEntry.total_sum() == Contract.total_sum()
        sum_credit = AccountingEntry.total_sum()
        return cls(contracts=all_contracts, sum_credit=sum_credit)


@dataclass
class InterestPerContract:
    contract: Contract
    contact: Contact
    interest: float
    balance: float
    interest_rows: List[InterestDataRow]


class InterestTransferListReport:
    def __init__(self, year, contracts):
        self.per_contract_data = [
            InterestPerContract(
                contract=contract,
                contact=contract.contact,
                interest=interest_processor.value,
                balance=interest_processor.balance,
                interest_rows=interest_processor.calculation_rows,
            ) for contract in contracts
            if len((interest_processor := InterestProcessor(contract, year)).calculation_rows) > 0
        ]
        self.sum_interest = Decimal(round(sum([data.interest for data in self.per_contract_data]),2))
        self.sum_salden = Decimal(round(sum([data.balance for data in self.per_contract_data]),2))


    @classmethod
    def create(cls, year, contact_id):
        if contact_id:
            return cls(year, contracts=Contract.objects.prefetch_related('contact').filter(Q(terminated_at__isnull=True) | Q(terminated_at__year__gt=year - 1)).filter(contact__number=contact_id).order_by('number'))
        return cls(year, contracts=Contract.objects.prefetch_related('contact').filter(Q(terminated_at__isnull=True) | Q(terminated_at__year__gt=year - 1)).order_by('contact__number', 'number'))


class RemainingCategory:
    def __init__(self):
        self.contracts: List[Tuple[Contract, Decimal]] = []
        self.balance_sum: Decimal = Decimal(0)

    def add(self, contract: Contract, balance: Decimal) -> None:
        self.contracts.append((contract, balance))
        self.balance_sum += balance


class RemainingContractsReport:
    def __init__(self, cutoff_date: datetime, contracts: List[Contract]):
        self.less_than_one: RemainingCategory = RemainingCategory()
        self.between_one_and_five: RemainingCategory = RemainingCategory()
        self.more_than_five: RemainingCategory = RemainingCategory()

        for contract in contracts:
            if contract.first_version.start > cutoff_date.date():
                continue
            balance = contract.balance_on(cutoff_date)
            if balance == 0:
                continue
            remaining_years = contract.remaining_years(cutoff_date.date())
            if remaining_years <= 1:
                self.less_than_one.add(contract, balance)
            elif remaining_years > 5:
                self.more_than_five.add(contract, balance)
            else:
                self.between_one_and_five.add(contract, balance)

    @classmethod
    def create(cls, cutoff_date: datetime):
        all_contracts = Contract.objects.order_by('number').prefetch_related('contact')
        return cls(cutoff_date, contracts=all_contracts)
