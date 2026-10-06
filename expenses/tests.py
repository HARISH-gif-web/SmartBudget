from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
import datetime

from .models import Category, Expense, Budget, SavingsGoal, Notification, UserProfile
from .utils import create_default_categories, check_budget_alerts


class ExpenseTrackerTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create primary test user
        self.user_a = User.objects.create_user(
            username='harish',
            email='harish@example.com',
            password='password123',
            first_name='Harish',
            last_name='Kumar'
        )
        self.profile_a = UserProfile.objects.create(user=self.user_a)
        create_default_categories(self.user_a)

        # Create secondary test user for data isolation testing
        self.user_b = User.objects.create_user(
            username='suresh',
            email='suresh@example.com',
            password='password123',
            first_name='Suresh',
            last_name='Rao'
        )
        self.profile_b = UserProfile.objects.create(user=self.user_b)
        create_default_categories(self.user_b)

        # Preload categories for user A
        self.cat_food = Category.objects.get(user=self.user_a, name='Food')
        self.cat_travel = Category.objects.get(user=self.user_a, name='Travel')

    # 1. Authentication Tests
    def test_user_registration(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'Anil Sharma',
            'email': 'anil@example.com',
            'username': 'anil',
            'password': 'secretpassword',
            'confirm_password': 'secretpassword',
            'terms': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='anil').exists())
        user = User.objects.get(username='anil')
        self.assertEqual(user.first_name, 'Anil')
        # Check default categories created
        self.assertTrue(Category.objects.filter(user=user, name='Food').exists())

    def test_user_login_with_username(self):
        response = self.client.post(reverse('login'), {
            'username_or_email': 'harish',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_user_login_with_email(self):
        response = self.client.post(reverse('login'), {
            'username_or_email': 'harish@example.com',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_user_logout(self):
        self.client.login(username='harish', password='password123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    # 2. Expense CRUD & Validation Tests
    def test_expense_creation(self):
        self.client.login(username='harish', password='password123')
        response = self.client.post(reverse('expense_add'), {
            'category': self.cat_food.id,
            'amount': '450.00',
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'notes': 'Lunch with friends',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Expense.objects.filter(user=self.user_a, amount=Decimal('450.00')).exists())

    def test_expense_zero_amount_rejection(self):
        self.client.login(username='harish', password='password123')
        response = self.client.post(reverse('expense_add'), {
            'category': self.cat_food.id,
            'amount': '0.00',
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'notes': 'Zero expense test',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'amount', 'Amount must be greater than zero.')

    def test_expense_negative_amount_rejection(self):
        self.client.login(username='harish', password='password123')
        response = self.client.post(reverse('expense_add'), {
            'category': self.cat_food.id,
            'amount': '-100.00',
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'notes': 'Negative test',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'amount', 'Amount must be greater than zero.')

    def test_expense_edit(self):
        self.client.login(username='harish', password='password123')
        exp = Expense.objects.create(
            user=self.user_a,
            category=self.cat_food,
            amount=Decimal('500.00'),
            date=timezone.now().date(),
            notes='Dinner'
        )
        response = self.client.post(reverse('expense_edit', args=[exp.id]), {
            'category': self.cat_food.id,
            'amount': '750.00',
            'date': exp.date.strftime('%Y-%m-%d'),
            'notes': 'Dinner with family',
        })
        self.assertEqual(response.status_code, 302)
        exp.refresh_from_db()
        self.assertEqual(exp.amount, Decimal('750.00'))
        self.assertEqual(exp.notes, 'Dinner with family')

    def test_expense_delete(self):
        self.client.login(username='harish', password='password123')
        exp = Expense.objects.create(
            user=self.user_a,
            category=self.cat_food,
            amount=Decimal('200.00'),
            date=timezone.now().date()
        )
        response = self.client.post(reverse('expense_delete', args=[exp.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Expense.objects.filter(id=exp.id).exists())

    # 3. Category CRUD Tests
    def test_category_crud(self):
        self.client.login(username='harish', password='password123')
        # Create
        response = self.client.post(reverse('category_add'), {
            'name': 'Gym & Fitness',
            'icon': '🏋️',
            'description': 'Monthly gym membership',
        })
        self.assertEqual(response.status_code, 302)
        cat = Category.objects.get(user=self.user_a, name='Gym & Fitness')
        self.assertEqual(cat.icon, '🏋️')

        # Edit
        response = self.client.post(reverse('category_edit', args=[cat.id]), {
            'name': 'Fitness & Sports',
            'icon': '⚽',
            'description': 'Updated description',
        })
        self.assertEqual(response.status_code, 302)
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Fitness & Sports')

        # Delete
        response = self.client.post(reverse('category_delete', args=[cat.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(id=cat.id).exists())

    # 4. Budget Alert Engine Tests (Section 34 Requirements)
    def test_budget_80_percent_warning(self):
        """
        Budget = ₹5,000, Spent = ₹4,000
        Expected = Warning, Usage = 80%
        """
        today = timezone.now().date()
        budget = Budget.objects.create(
            user=self.user_a,
            category=self.cat_food,
            amount=Decimal('5000.00'),
            month=today.month,
            year=today.year
        )
        Expense.objects.create(
            user=self.user_a,
            category=self.cat_food,
            amount=Decimal('4000.00'),
            date=today,
            notes='Major grocery trip'
        )

        self.assertEqual(budget.spent, Decimal('4000.00'))
        self.assertEqual(budget.usage_percentage, Decimal('80.0'))
        self.assertEqual(budget.status, 'warning')
        self.assertEqual(budget.status_label, 'Warning')

        # Check alert function triggers notification
        check_budget_alerts(self.user_a, self.cat_food, today.year, today.month)
        notif = Notification.objects.filter(user=self.user_a, notification_type='warning').first()
        self.assertIsNotNone(notif)
        self.assertIn('80.0% used', notif.title)

    def test_budget_100_percent_danger(self):
        """
        Budget = ₹5,000, Spent = ₹5,500
        Expected = Danger / Exceeded, Usage = 110%
        """
        today = timezone.now().date()
        budget = Budget.objects.create(
            user=self.user_a,
            category=self.cat_food,
            amount=Decimal('5000.00'),
            month=today.month,
            year=today.year
        )
        Expense.objects.create(
            user=self.user_a,
            category=self.cat_food,
            amount=Decimal('5500.00'),
            date=today,
            notes='Excessive dining'
        )

        self.assertEqual(budget.spent, Decimal('5500.00'))
        self.assertEqual(budget.usage_percentage, Decimal('110.0'))
        self.assertEqual(budget.status, 'danger')
        self.assertEqual(budget.status_label, 'Exceeded')

        # Check alert function triggers danger notification
        check_budget_alerts(self.user_a, self.cat_food, today.year, today.month)
        notif = Notification.objects.filter(user=self.user_a, notification_type='danger').first()
        self.assertIsNotNone(notif)
        self.assertIn('budget exceeded', notif.title)

    # 5. Savings Goals Tests
    def test_savings_goal_progress_and_deposit(self):
        """
        Target: ₹60,000, Saved: ₹25,000 -> 41.7%
        Deposit ₹10,000 -> Saved ₹35,000 -> 58.3%
        """
        goal = SavingsGoal.objects.create(
            user=self.user_a,
            name='New Laptop',
            target_amount=Decimal('60000.00'),
            saved_amount=Decimal('25000.00')
        )
        self.assertEqual(goal.progress_percentage, Decimal('41.7'))
        self.assertFalse(goal.is_completed)

        self.client.login(username='harish', password='password123')
        response = self.client.post(reverse('goal_deposit', args=[goal.id]), {
            'deposit_amount': '10000.00'
        })
        self.assertEqual(response.status_code, 302)
        goal.refresh_from_db()
        self.assertEqual(goal.saved_amount, Decimal('35000.00'))
        self.assertEqual(goal.progress_percentage, Decimal('58.3'))

    # 6. User Data Isolation & Security Tests
    def test_user_data_isolation(self):
        """Ensure User A cannot view, edit or delete User B's records."""
        cat_b = Category.objects.get(user=self.user_b, name='Food')
        exp_b = Expense.objects.create(
            user=self.user_b,
            category=cat_b,
            amount=Decimal('999.00'),
            date=timezone.now().date(),
            notes='Secret User B Expense'
        )

        # Log in as User A
        self.client.login(username='harish', password='password123')

        # User A views expense list -> shouldn't see User B's expense
        response = self.client.get(reverse('expense_list'))
        self.assertNotContains(response, 'Secret User B Expense')

        # User A tries to edit User B's expense -> returns 404
        edit_response = self.client.get(reverse('expense_edit', args=[exp_b.id]))
        self.assertEqual(edit_response.status_code, 404)

        # User A tries to delete User B's expense -> returns 404
        del_response = self.client.post(reverse('expense_delete', args=[exp_b.id]))
        self.assertEqual(del_response.status_code, 404)
        self.assertTrue(Expense.objects.filter(id=exp_b.id).exists())

    def test_unauthorized_access_redirects(self):
        """Unauthenticated requests must redirect to login."""
        protected_urls = [
            reverse('dashboard'),
            reverse('expense_list'),
            reverse('expense_add'),
            reverse('category_list'),
            reverse('budget_list'),
            reverse('analytics'),
            reverse('goals'),
            reverse('calendar'),
            reverse('notifications'),
            reverse('reports'),
            reverse('profile'),
            reverse('settings'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/login/'))
