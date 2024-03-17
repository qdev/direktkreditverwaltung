from django import forms
from .models import Contact, Contract, ContractVersion, AccountingEntry


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        exclude = ['updated_at', 'created_at']
        widgets = {
            'number': forms.NumberInput(),
            'email': forms.EmailInput(),
            'remark': forms.Textarea(),
        }
        labels = {
            'number': 'Nummer',
            "first_name": "Vorname",
            "last_name": "Nachname",
            "address": "Adresse",
            "phone": "Telefonnummer",
            "email": "E-Mail",
            "iban": "IBAN",
            "bic": "BIC",
            "bank_name": "Bankname",
            "remark": "Bemerkung",
        }


class ContractForm(forms.ModelForm):
    # These are fields from contract_version that are added in addition to the fields
    # from the contract model as a first contract version is created when
    # creating a contract.
    start = forms.DateField(
        input_formats=['%d.%m.%Y'],
        label="Start des Vertrags"
    )
    duration_months = forms.IntegerField(
        required=False,
        label="Laufzeit in Monaten"
    )
    cancellation_months = forms.IntegerField(
        required=False,
        label="Kündigungsfrist",
    )
    interest_rate = forms.FloatField(
        label="Zinssatz (Angabe in Prozent)"
    )
    interest_type = forms.ChoiceField(
        label="Art der Zinsrechnung",
        choices=[('ohne Zinseszins', 'ohne Zinseszins'), ('mit Zinseszins', 'mit Zinseszins'), ('direkte Auszahlung', 'direkte Auszahlung'),
                 ('ohne Zinseszins, Inflationlimit', 'ohne Zinseszins, Inflationlimit'), ('mit Zinseszins, Inflationlimit', 'mit Zinseszins, Inflationlimit'), ('direkte Auszahlung, Inflationlimit', 'direkte Auszahlung, Inflationlimit')]
    )

    class Meta:
        model = Contract
        exclude = ['updated_at', 'created_at']
        widgets = {
            'number': forms.NumberInput(),
            'comment': forms.Textarea(),
            'terminated_at': forms.DateInput(format='%d.%m.%Y'),
        }
        labels = {
            "number": "Nummer",
            "contact": "Kontakt/Vertragspartner_in",
            "comment": "Bemerkung",
            "category": "Kategorie",
            "interest_type": "Art der Zinsrechnung",
        }

    def __init__(self, *args, **kwargs):
        contact = kwargs.pop('contact')
        contract_version = kwargs.pop('contract_version')

        super(ContractForm, self).__init__(*args, **kwargs)

        self.fields['start'].widget.attrs['placeholder'] = "DD.MM.YYYY"
        if contact:
            self.fields['contact'].initial = contact
        if contract_version:
            self.fields['start'].initial = contract_version.start
            self.fields['duration_months'].initial = contract_version.duration_months
            self.fields['cancellation_months'].initial = contract_version.cancellation_months
            self.fields['interest_rate'].initial = contract_version.interest_rate * 100
            self.fields['interest_type'].initial = contract_version.interest_type

    def save(self, commit=True):
        contract = super(ContractForm, self).save(commit=commit)
        contract_version = None
        if contract.contractversion_set.count():
            # update existing contract
            contract_version = contract.last_version
            contract_version.start = self.cleaned_data['start']
            contract_version.duration_months = self.cleaned_data['duration_months']
            contract_version.cancellation_months = self.cleaned_data['cancellation_months']
            contract_version.interest_rate = self.cleaned_data['interest_rate'] / 100.0
            contract_version.interest_type = self.cleaned_data['interest_type']
        else:
            # create new contract - we need to create the first contract
            # version
            contract_version = ContractVersion(
                contract_id=contract.id,
                start=self.cleaned_data['start'],
                duration_months=self.cleaned_data['duration_months'],
                cancellation_months=self.cleaned_data['cancellation_months'],
                interest_rate=self.cleaned_data['interest_rate'] / 100.0,
                interest_type=self.cleaned_data['interest_type'],
                version=1,  # first version of contract
            )
        if contract_version and (contract_version.duration_months or contract_version.cancellation_months):
            contract_version.save()

        return contract


class ContractVersionForm(forms.ModelForm):
    interest_rate_percent = forms.FloatField(
        label="Zinssatz (Angabe in Prozent)"
    )

    class Meta:
        model = ContractVersion
        exclude = ['updated_at', 'created_at', 'interest_rate']
        widgets = {
            'start': forms.DateInput(format='%d.%m.%Y'),
            'duration_months': forms.NumberInput(),
            'cancellation_months': forms.NumberInput(),
        }
        labels = {
            'start': "Start der Vertragsversion",
            'duration_months': "Laufzeit in Monaten",
            'cancellation_months': "Kündigungsfrist",
            'contract': "Vertrag",
        }

    def __init__(self, *args, **kwargs):
        contract = kwargs.pop('contract')

        super(ContractVersionForm, self).__init__(*args, **kwargs)
        self.fields['start'].widget.attrs['placeholder'] = "DD.MM.YYYY"
        self.fields['contract'].initial = contract
        self.fields['version'].initial = contract.last_version.version + 1
        if self.instance and self.instance.id:
            self.fields['interest_rate_percent'].initial = self.instance.interest_rate * 100

    def save(self, commit=True):
        self.instance.interest_rate = self.cleaned_data['interest_rate_percent'] / 100.0

        contract_version = super(ContractVersionForm, self).save(commit=commit)
        return contract_version


class AccountingEntryForm(forms.ModelForm):
    class Meta:
        model = AccountingEntry
        exclude = ['updated_at', 'created_at']
        widgets = {
            'date': forms.DateInput(format='%d.%m.%Y'),
            'amount': forms.NumberInput(),
        }
        labels = {
            'contract': 'Vertrag',
            'date': 'Datum',
            'amount': 'Betrag (in Euro, Cents mit . abgetrennt)',
        }

    def __init__(self, *args, **kwargs):
        contract = kwargs.pop('contract')

        super(AccountingEntryForm, self).__init__(*args, **kwargs)
        self.fields['date'].widget.attrs['placeholder'] = "DD.MM.YYYY"
        self.fields['contract'].initial = contract
