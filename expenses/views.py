from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from decimal import Decimal
import calendar
import datetime
import csv

from .models import Expense, Category, Budget, SavingsGoal, Notification, UserProfile
from .forms import (
    UserRegistrationForm, UserLoginForm, ExpenseForm,
    CategoryForm, BudgetForm, SavingsGoalForm, SavingsDepositForm,
    UserProfileForm, UserSettingsForm
)
from .utils import create_default_categories, check_budget_alerts, get_financial_insights


def home(request):
    """Landing page for visitors."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


def register_view(request):
    """User registration page."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name'].strip()
            email = form.cleaned_data['email'].strip().lower()
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']

            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Create UserProfile
            UserProfile.objects.create(user=user)

            # Create default categories
            create_default_categories(user)

            # Create welcome notification
            Notification.objects.create(
                user=user,
                title="Welcome to Expense Tracker! 💰",
                message="Start by adding your first budget or expense to take control of your financial journey.",
                notification_type="success"
            )

            # Auto login
            login(request, user)
            messages.success(request, f"Welcome to Expense Tracker, {first_name or username}! Your account has been created.")
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    """User login page (allows username or email)."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['username_or_email'].strip()
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)

            # Check if identifier is email
            user_obj = None
            if '@' in identifier:
                try:
                    user_obj = User.objects.get(email__iexact=identifier)
                    username = user_obj.username
                except User.DoesNotExist:
                    username = identifier
            else:
                username = identifier

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if not remember_me:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, "Invalid username/email or password. Please try again.")
    else:
        form = UserLoginForm()

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')


@login_required
def dashboard(request):
    """Main dashboard page."""
    user = request.user
    today = timezone.now().date()

    # Selected month and year
    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        month = today.month
        year = today.year

    if month < 1 or month > 12:
        month = today.month

    month_name = calendar.month_name[month]

    # Filtered expenses for selected month
    monthly_expenses = Expense.objects.filter(
        user=user, date__year=year, date__month=month
    )
    total_spent = monthly_expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Budgets for selected month
    budgets = Budget.objects.filter(user=user, year=year, month=month).select_related('category')
    total_budget = budgets.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Remaining budget
    remaining_budget = total_budget - total_spent

    # Active savings goals total saved
    savings_goals = SavingsGoal.objects.filter(user=user)
    total_savings = savings_goals.aggregate(Sum('saved_amount'))['saved_amount__sum'] or Decimal('0.00')

    # Budget Usage by Category
    budget_usage_list = []
    for b in budgets:
        spent = b.spent
        remaining = b.remaining
        usage = b.usage_percentage
        status = b.status
        status_label = b.status_label
        budget_usage_list.append({
            'budget_id': b.id,
            'category': b.category,
            'budget_amount': b.amount,
            'spent_amount': spent,
            'remaining_amount': remaining,
            'usage_percentage': usage,
            'status': status,
            'status_label': status_label,
        })

    # Spending by Category for Chart.js
    category_spending = (
        monthly_expenses.values('category__name', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    
    chart_labels = []
    chart_data = []
    chart_colors = [
        '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
        '#8b5cf6', '#ec4899', '#06b6d4', '#6366f1'
    ]

    for item in category_spending:
        chart_labels.append(f"{item['category__icon']} {item['category__name']}")
        chart_data.append(float(item['total']))

    # Recent 5 expenses
    recent_expenses = Expense.objects.filter(user=user).select_related('category')[:5]

    # Upcoming Alerts
    alerts = []
    for b_item in budget_usage_list:
        if b_item['status'] == 'danger':
            alerts.append({
                'type': 'danger',
                'icon': '🔴',
                'text': f"{b_item['category'].name} budget exceeded ({b_item['usage_percentage']}% used)"
            })
        elif b_item['status'] == 'warning':
            alerts.append({
                'type': 'warning',
                'icon': '⚠️',
                'text': f"{b_item['category'].name} budget is {b_item['usage_percentage']}% used"
            })

    # Add general alerts if empty
    if not alerts:
        if total_budget > 0 and remaining_budget > 0:
            alerts.append({
                'type': 'normal',
                'icon': '🟢',
                'text': f"All categories are within budget for {month_name} {year}."
            })
        alerts.append({
            'type': 'success',
            'icon': '🎯',
            'text': "Great progress on your financial discipline!"
        })

    # Dynamic Financial Insights
    insights = get_financial_insights(user, year, month)

    # Generate Month Selector Options
    month_options = []
    for m in range(1, 13):
        month_options.append({
            'month': m,
            'name': calendar.month_name[m],
            'selected': (m == month and year == year)
        })

    context = {
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': month_name,
        'total_budget': total_budget,
        'total_spent': total_spent,
        'remaining_budget': remaining_budget,
        'total_savings': total_savings,
        'budget_usage_list': budget_usage_list,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'recent_expenses': recent_expenses,
        'alerts': alerts[:4],
        'insights': insights,
        'month_options': month_options,
    }

    return render(request, 'expenses/dashboard.html', context)


@login_required
def expense_list(request):
    """Full expense management list page with search, filters, and sorting."""
    user = request.user
    expenses = Expense.objects.filter(user=user).select_related('category')

    # Search filter
    q = request.GET.get('q', '').strip()
    if q:
        expenses = expenses.filter(
            Q(notes__icontains=q) |
            Q(category__name__icontains=q)
        )

    # Category filter
    category_id = request.GET.get('category', '').strip()
    if category_id:
        expenses = expenses.filter(category_id=category_id)

    # Date range filters
    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        expenses = expenses.filter(date__gte=date_from)

    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        expenses = expenses.filter(date__lte=date_to)

    # Sorting
    sort = request.GET.get('sort', 'date_desc')
    if sort == 'date_asc':
        expenses = expenses.order_by('date', 'created_at')
    elif sort == 'amount_desc':
        expenses = expenses.order_by('-amount')
    elif sort == 'amount_asc':
        expenses = expenses.order_by('amount')
    elif sort == 'category':
        expenses = expenses.order_by('category__name', '-date')
    else:
        expenses = expenses.order_by('-date', '-created_at')

    # Aggregations for the filtered set
    total_amount = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_count = expenses.count()

    # Pagination
    paginator = Paginator(expenses, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(user=user)

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'total_amount': total_amount,
        'total_count': total_count,
        'q': q,
        'selected_category': category_id,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
    }
    return render(request, 'expenses/expense_list.html', context)


@login_required
def expense_add(request):
    """Add a new expense."""
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()

            # Trigger alert calculation
            check_budget_alerts(request.user, expense.category, expense.date.year, expense.date.month)

            messages.success(request, f"Added expense of ₹{expense.amount} for {expense.category.name} successfully.")
            return redirect('expense_list')
    else:
        form = ExpenseForm(user=request.user)

    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Add New Expense'})


@login_required
def expense_edit(request, pk):
    """Edit an existing expense."""
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            expense = form.save()
            check_budget_alerts(request.user, expense.category, expense.date.year, expense.date.month)
            messages.success(request, "Expense updated successfully.")
            return redirect('expense_list')
    else:
        form = ExpenseForm(instance=expense, user=request.user)

    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Edit Expense', 'expense': expense})


@login_required
def expense_delete(request, pk):
    """Delete an expense."""
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        category = expense.category
        exp_year = expense.date.year
        exp_month = expense.date.month
        amount = expense.amount
        expense.delete()
        messages.success(request, f"Expense of ₹{amount} deleted successfully.")
        return redirect('expense_list')
    return render(request, 'expenses/expense_confirm_delete.html', {'expense': expense})


@login_required
def category_list(request):
    """List and manage user categories."""
    categories = Category.objects.filter(user=request.user).annotate(
        expense_count=Count('expenses'),
        total_spent=Sum('expenses__amount')
    )
    return render(request, 'expenses/category_list.html', {'categories': categories})


@login_required
def category_add(request):
    """Create a new category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            messages.success(request, f"Category '{cat.name}' created successfully.")
            return redirect('category_list')
    else:
        form = CategoryForm(user=request.user)
    return render(request, 'expenses/category_form.html', {'form': form, 'title': 'Add New Category'})


@login_required
def category_edit(request, pk):
    """Edit an existing category."""
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' updated successfully.")
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category, user=request.user)
    return render(request, 'expenses/category_form.html', {'form': form, 'title': 'Edit Category', 'category': category})


@login_required
def category_delete(request, pk):
    """Delete a category."""
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted successfully.")
        return redirect('category_list')
    return render(request, 'expenses/category_confirm_delete.html', {'category': category})


@login_required
def budget_list(request):
    """List monthly budgets."""
    user = request.user
    today = timezone.now().date()

    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        month = today.month
        year = today.year

    budgets = Budget.objects.filter(user=user, month=month, year=year).select_related('category')
    total_budget = budgets.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Compute spent and remaining for each
    budget_data = []
    total_spent = Decimal('0.00')
    for b in budgets:
        spent = b.spent
        total_spent += spent
        budget_data.append({
            'budget': b,
            'spent': spent,
            'remaining': b.remaining,
            'usage': b.usage_percentage,
            'status': b.status,
            'status_label': b.status_label
        })

    month_name = calendar.month_name[month]
    month_options = [{'month': m, 'name': calendar.month_name[m]} for m in range(1, 13)]

    context = {
        'budgets': budget_data,
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': month_name,
        'month_options': month_options,
        'total_budget': total_budget,
        'total_spent': total_spent,
        'remaining_budget': total_budget - total_spent,
    }
    return render(request, 'expenses/budget_list.html', context)


@login_required
def budget_add(request):
    """Create a new monthly budget."""
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, f"Budget of ₹{budget.amount} for {budget.category.name} created successfully.")
            return redirect('budget_list')
    else:
        form = BudgetForm(user=request.user)
    return render(request, 'expenses/budget_form.html', {'form': form, 'title': 'Create Monthly Budget'})


@login_required
def budget_edit(request, pk):
    """Edit a monthly budget."""
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            b = form.save()
            messages.success(request, f"Budget for {b.category.name} updated successfully.")
            return redirect('budget_list')
    else:
        form = BudgetForm(instance=budget, user=request.user)
    return render(request, 'expenses/budget_form.html', {'form': form, 'title': 'Edit Monthly Budget', 'budget': budget})


@login_required
def budget_delete(request, pk):
    """Delete a budget."""
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        cat_name = budget.category.name
        budget.delete()
        messages.success(request, f"Budget for {cat_name} deleted successfully.")
        return redirect('budget_list')
    return render(request, 'expenses/budget_confirm_delete.html', {'budget': budget})


@login_required
def analytics(request):
    """Detailed financial analytics and charts page."""
    user = request.user
    today = timezone.now().date()

    try:
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        year = today.year

    # 1. Monthly spending for the year (12 months)
    monthly_trend_labels = [calendar.month_abbr[m] for m in range(1, 13)]
    monthly_trend_data = []
    for m in range(1, 13):
        m_spent = Expense.objects.filter(
            user=user, date__year=year, date__month=m
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        monthly_trend_data.append(float(m_spent))

    # 2. Category spending breakdown for the year
    cat_breakdown = (
        Expense.objects.filter(user=user, date__year=year)
        .values('category__name', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    cat_labels = [f"{item['category__icon']} {item['category__name']}" for item in cat_breakdown]
    cat_data = [float(item['total']) for item in cat_breakdown]

    # 3. Overall Statistics
    total_expenses_year = Expense.objects.filter(user=user, date__year=year).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_tx_count = Expense.objects.filter(user=user, date__year=year).count()

    highest_cat = cat_breakdown.first() if cat_breakdown.exists() else None

    # Average daily spending
    # If current year, divide by days elapsed so far, else 365
    if year == today.year:
        days_elapsed = max(1, (today - datetime.date(year, 1, 1)).days + 1)
    else:
        days_elapsed = 365
    avg_daily_spending = round(total_expenses_year / Decimal(str(days_elapsed)), 2)

    # Current month's budget & remaining for quick stats
    current_month_budgets = Budget.objects.filter(user=user, year=year, month=today.month)
    current_total_budget = current_month_budgets.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    current_month_spent = Expense.objects.filter(user=user, date__year=year, date__month=today.month).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    current_remaining_budget = current_total_budget - current_month_spent

    context = {
        'selected_year': year,
        'year_options': [year - 1, year, year + 1],
        'monthly_trend_labels': monthly_trend_labels,
        'monthly_trend_data': monthly_trend_data,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
        'highest_category': highest_cat,
        'avg_daily_spending': avg_daily_spending,
        'total_expenses_year': total_expenses_year,
        'total_tx_count': total_tx_count,
        'current_total_budget': current_total_budget,
        'current_remaining_budget': current_remaining_budget,
    }
    return render(request, 'expenses/analytics.html', context)


@login_required
def goals(request):
    """Savings goals page."""
    user = request.user
    goals_list = SavingsGoal.objects.filter(user=user)
    deposit_form = SavingsDepositForm()

    total_target = goals_list.aggregate(Sum('target_amount'))['target_amount__sum'] or Decimal('0.00')
    total_saved = goals_list.aggregate(Sum('saved_amount'))['saved_amount__sum'] or Decimal('0.00')
    completed_count = sum(1 for g in goals_list if g.is_completed)

    context = {
        'goals': goals_list,
        'deposit_form': deposit_form,
        'total_target': total_target,
        'total_saved': total_saved,
        'completed_count': completed_count,
    }
    return render(request, 'expenses/goals.html', context)


@login_required
def goal_add(request):
    """Add a savings goal."""
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f"Savings goal '{goal.name}' created successfully.")
            return redirect('goals')
    else:
        form = SavingsGoalForm()
    return render(request, 'expenses/goal_form.html', {'form': form, 'title': 'Create Savings Goal'})


@login_required
def goal_edit(request, pk):
    """Edit a savings goal."""
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST, instance=goal)
        if form.is_valid():
            g = form.save()
            messages.success(request, f"Savings goal '{g.name}' updated successfully.")
            return redirect('goals')
    else:
        form = SavingsGoalForm(instance=goal)
    return render(request, 'expenses/goal_form.html', {'form': form, 'title': 'Edit Savings Goal', 'goal': goal})


@login_required
def goal_delete(request, pk):
    """Delete a savings goal."""
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        name = goal.name
        goal.delete()
        messages.success(request, f"Savings goal '{name}' deleted successfully.")
        return redirect('goals')
    return render(request, 'expenses/goal_confirm_delete.html', {'goal': goal})


@login_required
def goal_deposit(request, pk):
    """Add money to an existing savings goal."""
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsDepositForm(request.POST)
        if form.is_valid():
            deposit = form.cleaned_data['deposit_amount']
            goal.saved_amount += deposit
            goal.save()

            if goal.is_completed:
                Notification.objects.create(
                    user=request.user,
                    title=f"🎯 Goal Completed: {goal.name}!",
                    message=f"Congratulations! You reached your savings target of ₹{goal.target_amount:,.2f} for {goal.name}.",
                    notification_type="success"
                )
                messages.success(request, f"🎉 Congratulations! You have achieved your goal for '{goal.name}'!")
            else:
                messages.success(request, f"Added ₹{deposit:,.2f} to '{goal.name}'. Current progress: {goal.progress_percentage}%.")

            return redirect('goals')
    return redirect('goals')


@login_required
def calendar_view(request):
    """Monthly calendar showing expenses per day and details on click."""
    user = request.user
    today = timezone.now().date()

    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        month = today.month
        year = today.year

    # Previous and next month
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    # Month calendar matrix
    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    month_days = cal.monthdays2calendar(year, month)

    # Fetch expenses for the month
    expenses = Expense.objects.filter(user=user, date__year=year, date__month=month).select_related('category')

    # Map date string YYYY-MM-DD -> total amount and expense list
    day_expenses_map = {}
    day_totals = {}
    for exp in expenses:
        d_str = exp.date.strftime('%Y-%m-%d')
        if d_str not in day_expenses_map:
            day_expenses_map[d_str] = []
            day_totals[d_str] = Decimal('0.00')
        day_expenses_map[d_str].append({
            'id': exp.id,
            'category': exp.category.name,
            'icon': exp.category.icon,
            'amount': float(exp.amount),
            'notes': exp.notes or 'No notes',
            'date': exp.date.strftime('%d %b %Y'),
        })
        day_totals[d_str] += exp.amount

    # Build matrix with flags
    calendar_weeks = []
    for week in month_days:
        week_data = []
        for day, weekday in week:
            if day == 0:
                week_data.append({'day': 0, 'is_current_month': False})
            else:
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                spent = day_totals.get(date_str, Decimal('0.00'))
                is_today = (today.year == year and today.month == month and today.day == day)
                week_data.append({
                    'day': day,
                    'is_current_month': True,
                    'date_str': date_str,
                    'total_spent': spent,
                    'has_expenses': spent > 0,
                    'is_today': is_today,
                    'count': len(day_expenses_map.get(date_str, [])),
                })
        calendar_weeks.append(week_data)

    import json
    context = {
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': calendar.month_name[month],
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'calendar_weeks': calendar_weeks,
        'day_expenses_json': json.dumps(day_expenses_map),
        'total_month_spent': sum(day_totals.values(), Decimal('0.00')),
    }
    return render(request, 'expenses/calendar.html', context)


@login_required
def notifications_view(request):
    """In-app notifications center."""
    user = request.user
    notifications = Notification.objects.filter(user=user)

    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)

    unread_count = Notification.objects.filter(user=user, is_read=False).count()

    context = {
        'notifications': notifications,
        'filter_type': filter_type,
        'unread_count': unread_count,
    }
    return render(request, 'expenses/notifications.html', context)


@login_required
def notification_mark_read(request, pk):
    """Mark a single notification as read."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    messages.success(request, "Notification marked as read.")
    return redirect('notifications')


@login_required
def notification_mark_all_read(request):
    """Mark all notifications as read."""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notifications')


@login_required
def reports_view(request):
    """Financial reports and CSV export page."""
    user = request.user
    today = timezone.now().date()

    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        month = today.month
        year = today.year

    category_id = request.GET.get('category', '').strip()

    expenses = Expense.objects.filter(user=user, date__year=year, date__month=month).select_related('category')
    budgets = Budget.objects.filter(user=user, year=year, month=month).select_related('category')

    if category_id:
        expenses = expenses.filter(category_id=category_id)
        budgets = budgets.filter(category_id=category_id)

    total_budget = budgets.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    total_spent = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    remaining = total_budget - total_spent

    # Category breakdown
    cat_summary = (
        expenses.values('category__name', 'category__icon')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    categories = Category.objects.filter(user=user)
    month_options = [{'month': m, 'name': calendar.month_name[m]} for m in range(1, 13)]

    context = {
        'selected_month': month,
        'selected_year': year,
        'selected_month_name': calendar.month_name[month],
        'selected_category': category_id,
        'categories': categories,
        'month_options': month_options,
        'total_budget': total_budget,
        'total_spent': total_spent,
        'remaining': remaining,
        'cat_summary': cat_summary,
        'expenses': expenses,
    }
    return render(request, 'expenses/reports.html', context)


@login_required
def export_csv(request):
    """Export filtered expenses as a CSV file."""
    user = request.user
    today = timezone.now().date()

    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        month = today.month
        year = today.year

    category_id = request.GET.get('category', '').strip()

    expenses = Expense.objects.filter(user=user, date__year=year, date__month=month).select_related('category')
    if category_id:
        expenses = expenses.filter(category_id=category_id)

    response = HttpResponse(content_type='text/csv')
    filename = f"expense_report_{year}_{month:02d}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Date', 'Category', 'Amount (INR)', 'Notes', 'Created At'])

    for exp in expenses:
        writer.writerow([
            exp.id,
            exp.date.strftime('%Y-%m-%d'),
            exp.category.name,
            f"{exp.amount:.2f}",
            exp.notes or '',
            exp.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    return response


@login_required
def profile_view(request):
    """User profile management."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)

    total_expenses_count = Expense.objects.filter(user=request.user).count()
    active_goals_count = SavingsGoal.objects.filter(user=request.user).count()

    context = {
        'form': form,
        'profile': profile,
        'total_expenses_count': total_expenses_count,
        'active_goals_count': active_goals_count,
    }
    return render(request, 'expenses/profile.html', context)


@login_required
def settings_view(request):
    """Application preferences and settings."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved successfully.")
            return redirect('settings')
    else:
        form = UserSettingsForm(instance=profile)

    return render(request, 'expenses/settings.html', {'form': form, 'profile': profile})


@login_required
def toggle_dark_mode(request):
    """Toggle dark mode preference."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.dark_mode = not profile.dark_mode
    profile.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'dark_mode': profile.dark_mode})

    messages.info(request, f"Dark mode {'enabled' if profile.dark_mode else 'disabled'}.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


def help_view(request):
    """Help, FAQ, and documentation page."""
    return render(request, 'expenses/help.html')


# Error handlers
def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)


def handler403(request, exception):
    return render(request, '403.html', status=403)
