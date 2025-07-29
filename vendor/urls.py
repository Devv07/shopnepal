from django.urls import path
from . import views

app_name = 'vendor'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add-product/', views.add_product, name='add_product'),
    path('edit-product/<int:product_id>/', views.edit_product, name='edit_product'),
    path('delete-product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('create-category/', views.create_category, name='create_category'),
    path('edit-category/<int:category_id>/', views.edit_category, name='edit_category'),
    path('delete-category/<int:category_id>/', views.delete_category, name='delete_category'),
    path('manage-orders/', views.manage_orders, name='manage_orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('accept-order/<int:order_id>/', views.accept_order, name='accept_order'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('profile/', views.vendor_profile, name='vendor_profile'),
    path('analytics/', views.analytics, name='analytics'),
]