from decimal import Decimal
from django.db.models import Sum
from .models import Category, Expense, Budget, SavingsGoal, Notification, UserProfile
import calendar
from datetime import date


DEFAULT_CATEGORIES = [
    {"name": "Food", "icon": "🍔", "description": "Groceries, dining out, snacks & cafe"},
    {"name": "Travel", "icon": "✈️", "description": "Flights, fuel, taxi, transit & commute"},
    {"name": "Education", "icon": "🎓", "description": "Books, online courses, college & tuition"},
    {"name": "Shopping", "icon": "🛍️", "description": "Clothes, gadgets, gifts & personal care"},
    {"name": "Health", "icon": "🏥", "description": "Doctor appointments, medicines & gym"},
    {"name": "Entertainment", "icon": "🎬", "description": "Movies, concerts, gaming & streaming"},
    {"name": "Bills", "icon": "💡", "description": "Electricity, internet, water & rent"},
    {"name": "Groceries", "icon": "🛒", "description": "Supermarket, vegetables, daily essentials"},
]


def create_default_categories(user):
    """Create initial default categories for a new user."""
    for cat_data in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            user=user,
            name=cat_data["name"],
            defaults={
                "icon": cat_data["icon"],
                "description": cat_data["description"]
            }
        )


def check_budget_alerts(user, category, year, month):
    """Check budget usage for category and trigger appropriate notification."""
    try:
        budget = Budget.objects.get(user=user, category=category, year=year, month=month)
    except Budget.DoesNotExist:
        return

    spent = budget.spent
    usage = budget.usage_percentage

    if usage >= 100:
        title = f"🔴 {category.name} budget exceeded"
        message = f"You have exceeded your {category.name} budget for {calendar.month_name[month]} {year}. Spent ₹{spent:,.2f} of ₹{budget.amount:,.2f} ({usage}%)."
        if not Notification.objects.filter(user=user, title=title, is_read=False).exists():
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type="danger"
            )
    elif usage >= 80:
        title = f"⚠️ {category.name} budget is {usage}% used"
        message = f"Warning: You have used {usage}% of your {category.name} budget for {calendar.month_name[month]} {year}. Spent ₹{spent:,.2f} of ₹{budget.amount:,.2f}."
        if not Notification.objects.filter(user=user, title=title, is_read=False).exists():
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type="warning"
            )


def get_financial_insights(user, year, month):
    """Calculate intelligent financial insights dynamically from database."""
    insights = []

    # 1. Total spent this month vs Total budget
    expenses_this_month = Expense.objects.filter(user=user, date__year=year, date__month=month)
    total_spent = expenses_this_month.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    budgets_this_month = Budget.objects.filter(user=user, year=year, month=month)
    total_budget = budgets_this_month.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    # Month comparison
    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year
    expenses_prev_month = Expense.objects.filter(user=user, date__year=prev_year, date__month=prev_month)
    total_prev_spent = expenses_prev_month.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    if total_prev_spent > 0 and total_spent > 0:
        diff_pct = round(((total_spent - total_prev_spent) / total_prev_spent) * Decimal('100.0'), 1)
        if diff_pct > 0:
            insights.append({
                "icon": "📈",
                "text": f"Your overall spending is {diff_pct}% higher compared to {calendar.month_name[prev_month]} {prev_year}."
            })
        elif diff_pct < 0:
            insights.append({
                "icon": "📉",
                "text": f"Great job! You spent {abs(diff_pct)}% less overall compared to {calendar.month_name[prev_month]} {prev_year}."
            })

    # Highest spending category this month
    cat_spending = (
        expenses_this_month.values('category__name', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    if cat_spending.exists():
        top_cat = cat_spending.first()
        insights.append({
            "icon": "🔥",
            "text": f"{top_cat['category__icon']} {top_cat['category__name']} is your highest spending category this month (₹{top_cat['total']:,.2f})."
        })

        # Category comparison with last month for top category or Food
        top_cat_name = top_cat['category__name']
        prev_cat_spent = expenses_prev_month.filter(category__name=top_cat_name).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        if prev_cat_spent > 0:
            cat_diff = round(((top_cat['total'] - prev_cat_spent) / prev_cat_spent) * Decimal('100.0'), 1)
            if cat_diff > 5:
                insights.append({
                    "icon": "💡",
                    "text": f"You spent {cat_diff}% more on {top_cat_name} this month."
                })
            elif cat_diff < -5:
                insights.append({
                    "icon": "💡",
                    "text": f"You saved {abs(cat_diff)}% on {top_cat_name} compared to last month."
                })

    # Remaining monthly budget insight
    if total_budget > 0:
        remaining = total_budget - total_spent
        if remaining > 0:
            insights.append({
                "icon": "💰",
                "text": f"You have ₹{remaining:,.2f} remaining in your monthly budget for {calendar.month_name[month]}."
            })
        elif remaining < 0:
            insights.append({
                "icon": "⚠️",
                "text": f"You have exceeded your total monthly budget by ₹{abs(remaining):,.2f}."
            })

    # Categories within budget
    safe_categories = []
    for b in budgets_this_month:
        if b.usage_percentage < 80:
            safe_categories.append(b.category.name)
    if safe_categories:
        sample_cats = ", ".join(safe_categories[:2])
        insights.append({
            "icon": "🎯",
            "text": f"You are well within your {sample_cats} budget{'s' if len(safe_categories) > 1 else ''}."
        })

    # Savings goals insight
    goals = SavingsGoal.objects.filter(user=user)
    active_goals = [g for g in goals if not g.is_completed]
    completed_goals = [g for g in goals if g.is_completed]

    if completed_goals:
        insights.append({
            "icon": "🏆",
            "text": f"You've completed {len(completed_goals)} savings goal{'s' if len(completed_goals) > 1 else ''}! Fantastic discipline."
        })
    elif active_goals:
        best_progress_goal = max(active_goals, key=lambda g: g.progress_percentage)
        if best_progress_goal.progress_percentage > 0:
            insights.append({
                "icon": "🎯",
                "text": f"You're making great progress! {best_progress_goal.progress_percentage}% achieved on '{best_progress_goal.name}'."
            })

    # Fallback if no data yet
    if not insights:
        insights.append({
            "icon": "💡",
            "text": "Add your budgets and expenses to unlock personalized financial insights and smart spending tips."
        })
        insights.append({
            "icon": "🎯",
            "text": "Set category budgets to keep spending below the 80% warning threshold."
        })

    return insights[:4]
