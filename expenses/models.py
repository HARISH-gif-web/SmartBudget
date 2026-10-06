from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    currency = models.CharField(max_length=10, default='INR')
    currency_symbol = models.CharField(max_length=5, default='₹')
    dark_mode = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    monthly_budget_threshold = models.IntegerField(default=80)
    avatar_color = models.CharField(max_length=20, default='#2563eb')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def display_name(self):
        full_name = self.user.get_full_name()
        return full_name if full_name else self.user.username

    @property
    def initials(self):
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name[0]}{self.user.last_name[0]}".upper()
        elif self.user.first_name:
            return self.user.first_name[:2].upper()
        return self.user.username[:2].upper()


class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='📁')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_user_category')
        ]

    def __str__(self):
        return f"{self.icon} {self.name}"

    def total_spent(self, month=None, year=None):
        qs = self.expenses.all()
        if month and year:
            qs = qs.filter(date__year=year, date__month=month)
        elif year:
            qs = qs.filter(date__year=year)
        total = qs.aggregate(models.Sum('amount'))['amount__sum']
        return total or Decimal('0.00')


class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category.name} - ₹{self.amount} ({self.date})"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.IntegerField()  # 1 to 12
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-month', 'category__name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'month', 'year'], name='unique_user_category_budget')
        ]

    def __str__(self):
        return f"{self.category.name} - ₹{self.amount} ({self.month}/{self.year})"

    @property
    def spent(self):
        total = Expense.objects.filter(
            user=self.user,
            category=self.category,
            date__year=self.year,
            date__month=self.month
        ).aggregate(models.Sum('amount'))['amount__sum']
        return total or Decimal('0.00')

    @property
    def remaining(self):
        return self.amount - self.spent

    @property
    def usage_percentage(self):
        if self.amount <= 0:
            return Decimal('0.0')
        return round((self.spent / self.amount) * Decimal('100.0'), 1)

    @property
    def status(self):
        usage = self.usage_percentage
        if usage >= 100:
            return 'danger'
        elif usage >= 80:
            return 'warning'
        return 'normal'

    @property
    def status_label(self):
        status = self.status
        if status == 'danger':
            return 'Exceeded'
        elif status == 'warning':
            return 'Warning'
        return 'Normal'


class SavingsGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    name = models.CharField(max_length=150)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    saved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['deadline', '-created_at']

    def __str__(self):
        return f"{self.name} - ₹{self.saved_amount}/₹{self.target_amount}"

    @property
    def progress_percentage(self):
        if self.target_amount <= 0:
            return Decimal('0.0')
        pct = (self.saved_amount / self.target_amount) * Decimal('100.0')
        return round(min(Decimal('100.0'), pct), 1)

    @property
    def remaining(self):
        return max(Decimal('0.00'), self.target_amount - self.saved_amount)

    @property
    def is_completed(self):
        return self.saved_amount >= self.target_amount


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('normal', 'Normal'),
        ('warning', 'Warning'),
        ('danger', 'Danger'),
        ('info', 'Info'),
        ('success', 'Success'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title}"
