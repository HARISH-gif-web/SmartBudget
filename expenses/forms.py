from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import datetime
from .models import Expense, Category, Budget, SavingsGoal, UserProfile


class UserRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Harish Kumar',
            'id': 'reg_full_name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'name@example.com',
            'id': 'reg_email'
        })
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'id': 'reg_username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create strong password',
            'id': 'reg_password'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'id': 'reg_confirm_password'
        })
    )
    terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'reg_terms'
        }),
        error_messages={'required': 'You must agree to the Terms & Conditions to create an account.'}
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('This username is already taken. Please pick another.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email address already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', 'Passwords do not match. Please re-enter.')
            if len(password) < 6:
                self.add_error('password', 'Password must be at least 6 characters long.')
        return cleaned_data


class UserLoginForm(forms.Form):
    username_or_email = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email',
            'id': 'login_username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'id': 'login_password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'login_remember'
        })
    )


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['amount', 'category', 'date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01',
                'id': 'expense_amount'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'expense_date'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'id': 'expense_category'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'e.g. Lunch with friends, flight ticket, books...',
                'id': 'expense_notes'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['category'].empty_label = 'Select Category ▼'
        if not self.initial.get('date'):
            self.initial['date'] = timezone.now().date()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise ValidationError('Amount must be greater than zero.')
        return amount

    def clean_category(self):
        category = self.cleaned_data.get('category')
        if not category:
            raise ValidationError('Please select a valid expense category.')
        return category

    def clean_date(self):
        exp_date = self.cleaned_data.get('date')
        if not exp_date:
            raise ValidationError('Please provide a valid expense date.')
        return exp_date


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category Name (e.g. Groceries, Gym)',
                'id': 'category_name'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Icon or Emoji (e.g. 🍔, ✈️, 🛒)',
                'id': 'category_icon'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Short description of this category',
                'id': 'category_description'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Category name is required.')
        qs = Category.objects.filter(user=self.user, name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f'Category "{name}" already exists.')
        return name


class BudgetForm(forms.ModelForm):
    MONTH_CHOICES = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]

    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'budget_month'})
    )
    year = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'budget_year'})
    )

    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'year']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select', 'id': 'budget_category'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Budget Amount (₹)',
                'step': '1.00',
                'min': '1.00',
                'id': 'budget_amount'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(user=self.user)
        self.fields['category'].empty_label = 'Select Category ▼'
        today = timezone.now().date()
        if not self.initial.get('month'):
            self.initial['month'] = today.month
        if not self.initial.get('year'):
            self.initial['year'] = today.year

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise ValidationError('Budget amount must be greater than zero.')
        return amount

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')

        if category and month and year and self.user:
            qs = Budget.objects.filter(user=self.user, category=category, month=month, year=year)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                month_name = datetime.date(2000, int(month), 1).strftime('%B')
                raise ValidationError(f'A budget for {category.name} in {month_name} {year} already exists.')
        return cleaned_data


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['name', 'target_amount', 'saved_amount', 'deadline']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Goal Name (e.g. New Laptop, Emergency Fund)',
                'id': 'goal_name'
            }),
            'target_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Target Amount (₹)',
                'step': '100.00',
                'min': '1.00',
                'id': 'goal_target_amount'
            }),
            'saved_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Currently Saved (₹)',
                'step': '50.00',
                'min': '0.00',
                'id': 'goal_saved_amount'
            }),
            'deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'goal_deadline'
            }),
        }

    def clean_target_amount(self):
        target = self.cleaned_data.get('target_amount')
        if target is None or target <= Decimal('0.00'):
            raise ValidationError('Target amount must be greater than zero.')
        return target

    def clean_saved_amount(self):
        saved = self.cleaned_data.get('saved_amount')
        if saved is None or saved < Decimal('0.00'):
            return Decimal('0.00')
        return saved


class SavingsDepositForm(forms.Form):
    deposit_amount = forms.DecimalField(
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Amount to deposit (₹)',
            'step': '50.00',
            'id': 'deposit_amount'
        })
    )


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = UserProfile
        fields = ['currency', 'currency_symbol', 'avatar_color']
        widgets = {
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'currency_symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar_color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile.save()
        return profile


class UserSettingsForm(forms.ModelForm):
    CURRENCY_CHOICES = [
        ('INR', '₹ INR - Indian Rupee'),
        ('USD', '$ USD - US Dollar'),
        ('EUR', '€ EUR - Euro'),
        ('GBP', '£ GBP - British Pound'),
        ('CAD', '$ CAD - Canadian Dollar'),
        ('AUD', '$ AUD - Australian Dollar'),
    ]

    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'setting_currency'})
    )

    class Meta:
        model = UserProfile
        fields = ['dark_mode', 'email_notifications', 'monthly_budget_threshold', 'currency']
        widgets = {
            'dark_mode': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'setting_dark_mode'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'setting_email_notifications'}),
            'monthly_budget_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '50',
                'max': '100',
                'id': 'setting_threshold'
            }),
        }
