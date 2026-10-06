from django.contrib import admin
from .models import Expense, Category, Budget, SavingsGoal, Notification, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'currency', 'currency_symbol', 'dark_mode', 'email_notifications', 'monthly_budget_threshold')
    search_fields = ('user__username', 'user__email')
    list_filter = ('dark_mode', 'currency')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'user', 'created_at')
    search_fields = ('name', 'user__username')
    list_filter = ('created_at',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'amount', 'date', 'notes', 'created_at')
    search_fields = ('notes', 'category__name', 'user__username')
    list_filter = ('date', 'category', 'created_at')
    date_hierarchy = 'date'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'amount', 'month', 'year', 'created_at')
    search_fields = ('category__name', 'user__username')
    list_filter = ('year', 'month', 'category')


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'target_amount', 'saved_amount', 'deadline', 'created_at')
    search_fields = ('name', 'user__username')
    list_filter = ('deadline', 'created_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    list_filter = ('notification_type', 'is_read', 'created_at')
