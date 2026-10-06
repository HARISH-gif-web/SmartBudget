from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('expenses.urls')),
]

handler404 = 'expenses.views.handler404'
handler500 = 'expenses.views.handler500'
handler403 = 'expenses.views.handler403'
