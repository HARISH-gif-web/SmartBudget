from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal
import datetime

from expenses.models import Category, Expense, Budget, SavingsGoal, Notification, UserProfile
from expenses.utils import create_default_categories


class Command(BaseCommand):
    help = 'Populates the database with demo user Harish and realistic financial records matching October 2026.'

    def handle(self, *args, **options):
        # Create demo user Harish
        user, created = User.objects.get_or_create(
            username='harish',
            defaults={
                'email': 'harish@example.com',
                'first_name': 'Harish',
                'last_name': 'Kumar',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        user.set_password('password123')
        user.save()

        # User profile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.currency = 'INR'
        profile.currency_symbol = '₹'
        profile.dark_mode = False
        profile.save()

        # Clear existing data for a clean slate
        Expense.objects.filter(user=user).delete()
        Budget.objects.filter(user=user).delete()
        SavingsGoal.objects.filter(user=user).delete()
        Notification.objects.filter(user=user).delete()

        # Default Categories
        create_default_categories(user)

        cat_food = Category.objects.get(user=user, name='Food')
        cat_travel = Category.objects.get(user=user, name='Travel')
        cat_education = Category.objects.get(user=user, name='Education')
        cat_shopping = Category.objects.get(user=user, name='Shopping')

        # 1. Budgets for October 2026 (Month 10, Year 2026)
        # Total Budget = 5000 + 3000 + 4000 + 3000 = 15,000
        Budget.objects.create(user=user, category=cat_food, amount=Decimal('5000.00'), month=10, year=2026)
        Budget.objects.create(user=user, category=cat_travel, amount=Decimal('3000.00'), month=10, year=2026)
        Budget.objects.create(user=user, category=cat_education, amount=Decimal('4000.00'), month=10, year=2026)
        Budget.objects.create(user=user, category=cat_shopping, amount=Decimal('3000.00'), month=10, year=2026)

        # 2. Expenses for October 2026
        # Target totals:
        # Food: 4,200 (450 + 750 + 1200 + 1800)
        # Travel: 1,500 (60 + 440 + 1000)
        # Education: 4,100 (550 + 1550 + 2000)
        # Shopping: 700 (200 + 500)
        # Total Spent = 4200 + 1500 + 4100 + 700 = 10,500
        # Remaining = 15,000 - 10,500 = 4,500

        # Food (4,200)
        Expense.objects.create(user=user, category=cat_food, amount=Decimal('450.00'), date=datetime.date(2026, 10, 6), notes='Lunch with friends')
        Expense.objects.create(user=user, category=cat_food, amount=Decimal('750.00'), date=datetime.date(2026, 10, 5), notes='Weekly vegetables & fruits')
        Expense.objects.create(user=user, category=cat_food, amount=Decimal('1200.00'), date=datetime.date(2026, 10, 3), notes='Family dinner at restaurant')
        Expense.objects.create(user=user, category=cat_food, amount=Decimal('1800.00'), date=datetime.date(2026, 10, 1), notes='Monthly supermarket grocery haul')

        # Travel (1,500)
        Expense.objects.create(user=user, category=cat_travel, amount=Decimal('60.00'), date=datetime.date(2026, 10, 5), notes='Bus Ticket')
        Expense.objects.create(user=user, category=cat_travel, amount=Decimal('440.00'), date=datetime.date(2026, 10, 4), notes='Uber cab ride to station')
        Expense.objects.create(user=user, category=cat_travel, amount=Decimal('1000.00'), date=datetime.date(2026, 10, 2), notes='Metro card & fuel reload')

        # Education (4,100 - Exceeded 102%)
        Expense.objects.create(user=user, category=cat_education, amount=Decimal('550.00'), date=datetime.date(2026, 10, 4), notes='Python Book')
        Expense.objects.create(user=user, category=cat_education, amount=Decimal('1550.00'), date=datetime.date(2026, 10, 3), notes='Advanced Django Certification')
        Expense.objects.create(user=user, category=cat_education, amount=Decimal('2000.00'), date=datetime.date(2026, 10, 2), notes='Quarterly course materials & books')

        # Shopping (700)
        Expense.objects.create(user=user, category=cat_shopping, amount=Decimal('200.00'), date=datetime.date(2026, 10, 3), notes='T-shirt')
        Expense.objects.create(user=user, category=cat_shopping, amount=Decimal('500.00'), date=datetime.date(2026, 10, 2), notes='Desk organizer & notebook')

        # 3. Savings Goals
        # New Laptop (Target 60,000, Saved 25,000)
        SavingsGoal.objects.create(
            user=user,
            name='New Laptop',
            target_amount=Decimal('60000.00'),
            saved_amount=Decimal('25000.00'),
            deadline=datetime.date(2026, 12, 31)
        )
        # Emergency Fund (Target 50,000, Saved 0)
        SavingsGoal.objects.create(
            user=user,
            name='Emergency Fund',
            target_amount=Decimal('50000.00'),
            saved_amount=Decimal('0.00'),
            deadline=datetime.date(2027, 3, 31)
        )

        # 4. Notifications
        Notification.objects.create(
            user=user,
            title='🔴 Education budget exceeded',
            message='You have exceeded your Education budget for October 2026. Spent ₹4,100.00 of ₹4,000.00 (102.5%).',
            notification_type='danger',
            is_read=False
        )
        Notification.objects.create(
            user=user,
            title='⚠️ Food budget is 84% used',
            message='Warning: You have used 84.0% of your Food budget for October 2026. Spent ₹4,200.00 of ₹5,000.00.',
            notification_type='warning',
            is_read=False
        )
        Notification.objects.create(
            user=user,
            title='🎯 Great progress on your Emergency Fund!',
            message='You have reached 70% of your Emergency Fund target! Keep up the great saving habit.',
            notification_type='success',
            is_read=True
        )
        Notification.objects.create(
            user=user,
            title='Welcome to Expense Tracker! 💰',
            message='Track smarter, spend better, and take full control of your financial future.',
            notification_type='info',
            is_read=True
        )

        self.stdout.write(self.style.SUCCESS(
            'Demo data seeded successfully for user "harish" (password: "password123")!'
        ))
