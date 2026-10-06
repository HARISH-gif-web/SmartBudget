from datetime import date
from .models import Notification, UserProfile


def expense_context(request):
    """Provides common global context variables across all templates."""
    context = {
        'APP_NAME': 'Expense Tracker',
        'APP_TAGLINE': 'Track Smarter. Spend Better.',
        'CURRENCY_SYMBOL': '₹',
        'CURRENT_YEAR': date.today().year,
        'CURRENT_MONTH': date.today().month,
        'unread_notifications_count': 0,
        'user_profile': None,
        'user_initials': 'U',
    }

    if request.user.is_authenticated:
        # Get or create profile
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        context['user_profile'] = profile
        context['CURRENCY_SYMBOL'] = profile.currency_symbol or '₹'
        context['unread_notifications_count'] = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        context['user_initials'] = profile.initials

    return context
