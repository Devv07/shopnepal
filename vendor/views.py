from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.contrib import messages
from .models import Category, Product
from user.models import Order, OrderItem, Review
from .forms import ProductForm, CategoryForm, VendorProfileForm
from django.db.models import Sum, Avg
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied. Vendor account must be verified.')
        return redirect('user:home')
    
    products = Product.objects.filter(vendor=request.user)
    low_stock_products = products.filter(stock__lte=5)
    orders = Order.objects.filter(items__product__vendor=request.user).distinct()
    new_orders = orders.filter(status='pending').count()
    
    avg_rating = Review.objects.filter(product__vendor=request.user).aggregate(avg=Avg('rating'))['avg'] or 0
    
    stats = {
        'active_products': products.count(),
        'total_orders': orders.count(),
        'total_revenue': orders.filter(status__in=['accepted', 'completed']).aggregate(total=Sum('total_amount'))['total'] or 0,
        'average_rating': avg_rating,
        'sales_data': json.dumps([12000, 19000, 15000, 25000, 22000, 30000]),
    }
    return render(request, 'vendor/dashboard.html', {
        'products': products,
        'low_stock_products': low_stock_products,
        'new_orders': new_orders,
        'stats': stats,
    })

@login_required
def add_product(request):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied. Vendor account must be verified.')
        return redirect('core:home')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user
            product.save()
            messages.success(request, 'Product added successfully!')
            return redirect('vendor:dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ProductForm(user=request.user)
    return render(request, 'vendor/product_add.html', {'form': form})

@login_required
def edit_product(request, product_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    product = get_object_or_404(Product, id=product_id, vendor=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('vendor:dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ProductForm(instance=product, user=request.user)
    return render(request, 'vendor/edit_product.html', {'form': form, 'product': product})

@login_required
def delete_product(request, product_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    product = get_object_or_404(Product, id=product_id, vendor=request.user)
    product.delete()
    messages.success(request, 'Product deleted successfully!')
    return redirect('vendor:dashboard')

@login_required
def create_category(request):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('vendor:dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CategoryForm()
    return render(request, 'vendor/create_category.html', {'form': form})

@login_required
def edit_category(request, category_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('vendor:dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CategoryForm(instance=category)
    return render(request, 'vendor/edit_category.html', {'form': form, 'category': category})

@login_required
def delete_category(request, category_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    category = get_object_or_404(Category, id=category_id)
    category.delete()
    messages.success(request, 'Category deleted successfully!')
    return redirect('vendor:dashboard')

@login_required
def manage_orders(request):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    orders = Order.objects.filter(items__product__vendor=request.user).distinct().order_by('-created_at')
    orders_data = []
    for order in orders:
        order_items = [
            {
                'product': item.product,
                'quantity': item.quantity,
                'price': item.price,
                'subtotal': item.quantity * item.price
            }
            for item in order.items.filter(product__vendor=request.user)
        ]
        orders_data.append({
            'id': order.id,
            'status': order.status,
            'total_amount': order.total_amount,
            'order_items': order_items
        })
    return render(request, 'vendor/manage_orders.html', {'orders': orders_data})

@login_required
def order_detail(request, order_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    try:
        order = Order.objects.filter(id=order_id, items__product__vendor=request.user).distinct().first()
        if not order:
            logger.error(f"No order found with id={order_id} for vendor={request.user.email}")
            raise Http404("Order not found or you do not have permission to view it.")
        items = [
            {
                'product': item.product,
                'quantity': item.quantity,
                'price': item.price,
                'subtotal': item.quantity * item.price
            }
            for item in order.items.filter(product__vendor=request.user)
        ]
        return render(request, 'vendor/order_detail.html', {'order': order, 'items': items})
    except Order.MultipleObjectsReturned:
        logger.error(f"Multiple orders found for id={order_id}, vendor={request.user.email}")
        messages.error(request, 'Multiple orders found for this ID. Please contact support.')
        return redirect('vendor:manage_orders')

@login_required
def accept_order(request, order_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    try:
        order = Order.objects.filter(id=order_id, items__product__vendor=request.user).distinct().first()
        if not order:
            logger.error(f"No order found with id={order_id} for vendor={request.user.email}")
            raise Http404("Order not found or you do not have permission to modify it.")
        if order.status == 'pending':
            order.status = 'accepted'
            order.save()
            messages.success(request, 'Order accepted successfully!')
        else:
            messages.error(request, 'Order cannot be accepted in its current state.')
        return redirect('vendor:manage_orders')
    except Order.MultipleObjectsReturned:
        logger.error(f"Multiple orders found for id={order_id}, vendor={request.user.email}")
        messages.error(request, 'Multiple orders found for this ID. Please contact support.')
        return redirect('vendor:manage_orders')

@login_required
def cancel_order(request, order_id):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    try:
        order = Order.objects.filter(id=order_id, items__product__vendor=request.user).distinct().first()
        if not order:
            logger.error(f"No order found with id={order_id} for vendor={request.user.email}")
            raise Http404("Order not found or you do not have permission to modify it.")
        if order.status == 'pending':
            order.status = 'canceled'
            order.save()
            messages.success(request, 'Order canceled successfully!')
        else:
            messages.error(request, 'Order cannot be canceled in its current state.')
        return redirect('vendor:manage_orders')
    except Order.MultipleObjectsReturned:
        logger.error(f"Multiple orders found for id={order_id}, vendor={request.user.email}")
        messages.error(request, 'Multiple orders found for this ID. Please contact support.')
        return redirect('vendor:manage_orders')

@login_required
def vendor_profile(request):
    if request.user.role != 'vendor':
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    if request.method == 'POST':
        form = VendorProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('vendor:vendor_profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = VendorProfileForm(instance=request.user)
    return render(request, 'vendor/vendor_profile.html', {'form': form})

@login_required
def analytics(request):
    if request.user.role != 'vendor' or not request.user.is_verified:
        messages.error(request, 'Access denied.')
        return redirect('core:home')
    
    orders = Order.objects.filter(items__product__vendor=request.user, status__in=['accepted', 'completed']).distinct()
    sales_data = []
    for month in range(1, 7):
        monthly_total = orders.filter(created_at__month=month).aggregate(total=Sum('total_amount'))['total'] or 0
        sales_data.append(float(monthly_total))
    
    context = {
        'stats': {
            'sales_data': json.dumps(sales_data)
        }
    }
    return render(request, 'vendor/analytics.html', context)