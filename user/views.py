from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.contrib import messages
from .models import Cart, Wishlist, Order, OrderItem, Review
from vendor.models import Category, Product
from .forms import UserProfileForm
from django.db import transaction, IntegrityError
from django.db.models import Avg
import uuid
import requests
import logging
import hmac
import hashlib
import base64
import json
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

def home(request):
    categories = Category.objects.all()[:8]
    featured_products = Product.objects.filter(stock__gt=0).order_by('-created_at')[:4]
    best_sellers = Product.objects.filter(stock__gt=0).order_by('-id')[:8]
    return render(request, 'user/home.html', {
        'categories': categories,
        'filtered_products': featured_products,
        'best_sellers': best_sellers,
    })

@login_required
def dashboard(request):
    recommended_products = Product.objects.filter(
        review__isnull=False
    ).annotate(avg_rating=Avg('review__rating')).order_by('-avg_rating')[:4]
    return render(request, 'user/home.html', {
        'recommended_products': recommended_products,
    })

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'user/order_history.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        return render(request, 'user/order_detail.html', {'order': order})
    except Order.DoesNotExist:
        raise Http404("Order not found")

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('user:profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'user/profile.html', {'form': form})

@login_required
def cart(request):
    cart_items = Cart.objects.filter(user=request.user)
    cart_data = []
    total_amount = 0
    
    for item in cart_items:
        price = item.product.discount_price if item.product.discount_price else item.product.price
        subtotal = item.quantity * price
        total_amount += subtotal
        cart_data.append({
            'item': item,
            'subtotal': subtotal,
        })
    
    return render(request, 'user/cart.html', {
        'cart_data': cart_data,
        'total_amount': total_amount,
    })

@login_required
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user)
    return render(request, 'user/wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def product_list(request):
    category_id = request.GET.get('category')
    query = request.GET.get('q')
    categories = Category.objects.all()
    products = Product.objects.filter(stock__gt=0)
    if category_id:
        products = products.filter(category_id=category_id)
    if query:
        products = products.filter(name__icontains=query)
    return render(request, 'user/product_list.html', {
        'categories': categories,
        'products': products,
        'selected_category': category_id,
        'search_query': query,
    })

@login_required
def product_detail(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        return render(request, 'user/product_detail.html', {'product': product})
    except Product.DoesNotExist:
        raise Http404("Product not found")

@login_required
def add_to_cart(request, product_id):
    if request.user.role != 'user':
        messages.error(request, 'Only users can add to cart.')
        return redirect('user:product_list')
    try:
        product = Product.objects.get(id=product_id)
        if product.stock < 1:
            messages.error(request, 'Product is out of stock.')
            return redirect('user:product_list')
        cart_item, created = Cart.objects.get_or_create(user=request.user, product=product)
        if not created:
            if cart_item.quantity + 1 > product.stock:
                messages.error(request, 'Cannot add more items than available stock.')
                return redirect('user:cart')
            cart_item.quantity += 1
            cart_item.save()
        messages.success(request, f'{product.name} added to cart!')
        return redirect('user:cart')
    except Product.DoesNotExist:
        raise Http404("Product not found")

@login_required
def add_to_wishlist(request, product_id):
    if request.user.role != 'user':
        messages.error(request, 'Only users can add to wishlist.')
        return redirect('user:product_list')
    try:
        product = Product.objects.get(id=product_id)
        Wishlist.objects.get_or_create(user=request.user, product=product)
        messages.success(request, f'{product.name} added to wishlist!')
        return redirect('user:wishlist')
    except Product.DoesNotExist:
        raise Http404("Product not found")

@login_required
def remove_from_cart(request, cart_id):
    try:
        cart_item = Cart.objects.get(id=cart_id, user=request.user)
        cart_item.delete()
        messages.success(request, 'Product removed from cart.')
        return redirect('user:cart')
    except Cart.DoesNotExist:
        raise Http404("Cart item not found")

@login_required
def remove_from_wishlist(request, wishlist_id):
    try:
        wishlist_item = Wishlist.objects.get(id=wishlist_id, user=request.user)
        wishlist_item.delete()
        messages.success(request, 'Product removed from wishlist.')
        return redirect('user:wishlist')
    except Wishlist.DoesNotExist:
        raise Http404("Wishlist item not found")

@login_required
def update_cart(request, cart_id):
    try:
        cart_item = Cart.objects.get(id=cart_id, user=request.user)
        if request.method == 'POST':
            quantity = int(request.POST.get('quantity', 1))
            if quantity > 0 and quantity <= cart_item.product.stock:
                cart_item.quantity = quantity
                cart_item.save()
                messages.success(request, 'Cart updated successfully.')
            else:
                messages.error(request, 'Invalid quantity or insufficient stock.')
        return redirect('user:cart')
    except Cart.DoesNotExist:
        raise Http404("Cart item not found")

@login_required
def checkout(request):
    product_id = request.GET.get('product')
    quantity = request.GET.get('quantity', 1)
    if product_id:
        try:
            product = Product.objects.get(id=product_id)
            if product.stock < int(quantity):
                messages.error(request, 'Insufficient stock for this product.')
                return redirect('user:cart')
            price = product.discount_price if product.discount_price else product.price
            subtotal = int(quantity) * price
            cart_data = [{
                'product': product,
                'quantity': int(quantity),
                'price': price,
                'subtotal': subtotal
            }]
            total_amount = subtotal
        except Product.DoesNotExist:
            messages.error(request, 'Product not found.')
            return redirect('user:cart')
    else:
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items:
            messages.error(request, 'Your cart is empty.')
            return redirect('user:cart')
        cart_data = []
        total_amount = 0
        for item in cart_items:
            price = item.product.discount_price if item.product.discount_price else item.product.price
            subtotal = item.quantity * price
            total_amount += subtotal
            cart_data.append({
                'product': item.product,
                'quantity': item.quantity,
                'price': price,
                'subtotal': subtotal
            })
    
    return render(request, 'user/checkout.html', {
        'cart_data': cart_data,
        'total_amount': total_amount,
    })

@login_required
def place_order(request):
    if request.user.role != 'user':
        messages.error(request, 'Only users can place orders.')
        return redirect('user:product_list')
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity', 1)
        
        # Prepare cart items
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
                if product.stock < int(quantity):
                    messages.error(request, f'Insufficient stock for {product.name}. Available: {product.stock}.')
                    return redirect('user:cart')
                cart_items = [{'product': product, 'quantity': int(quantity), 'price': product.discount_price or product.price}]
                total_amount = cart_items[0]['quantity'] * cart_items[0]['price']
            except Product.DoesNotExist:
                messages.error(request, 'Product not found.')
                return redirect('user:cart')
        else:
            cart_items = Cart.objects.filter(user=request.user)
            if not cart_items:
                messages.error(request, 'Your cart is empty.')
                return redirect('user:cart')
            cart_items = [{'product': item.product, 'quantity': item.quantity, 'price': item.product.discount_price or item.product.price} for item in cart_items]
            # Validate stock for all cart items
            for item in cart_items:
                if item['product'].stock < item['quantity']:
                    messages.error(request, f'Insufficient stock for {item["product"].name}. Available: {item["product"].stock}.')
                    return redirect('user:cart')
            total_amount = sum(item['quantity'] * item['price'] for item in cart_items)
        
        # Create order and update stock atomically
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    total_amount=total_amount,
                    status='pending',
                    esewa_pid=str(uuid.uuid4()) if payment_method == 'esewa' else None
                )
                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item['product'],
                        quantity=item['quantity'],
                        price=item['price']
                    )
                    # Update stock
                    item['product'].stock -= item['quantity']
                    if item['product'].stock < 0:
                        raise ValueError(f"Stock cannot be negative for {item['product'].name}")
                    item['product'].save()
        
                if payment_method == 'esewa':
                    esewa_url = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
                    params = {
                        'amount': float(total_amount),
                        'tax_amount': 0,
                        'total_amount': float(total_amount),
                        'transaction_uuid': order.esewa_pid,
                        'product_code': settings.ESEWA_MERCHANT_ID,
                        'product_service_charge': 0,
                        'product_delivery_charge': 0,
                        'success_url': request.build_absolute_uri(reverse('user:esewa_verify')),
                        'failure_url': request.build_absolute_uri(reverse('user:checkout')),
                        'signed_field_names': 'total_amount,transaction_uuid,product_code',
                        'signature': ''
                    }
                    # Generate HMAC SHA256 signature
                    signature_string = f"total_amount={params['total_amount']},transaction_uuid={params['transaction_uuid']},product_code={params['product_code']}"
                    signature = hmac.new(
                        key=settings.ESEWA_SECRET_KEY.encode('utf-8'),
                        msg=signature_string.encode('utf-8'),
                        digestmod=hashlib.sha256
                    ).digest()
                    params['signature'] = base64.b64encode(signature).decode('utf-8')
                    logger.debug(f"Redirecting to eSewa with params: {params}")
                    return render(request, 'user/esewa_redirect.html', {'esewa_url': esewa_url, 'params': params})
                
                elif payment_method == 'cod':
                    order.status = 'pending'
                    order.save()
                    Cart.objects.filter(user=request.user).delete()
                    messages.success(request, 'Order placed successfully with Cash on Delivery!')
                    return redirect('user:order_confirmation', order_id=order.id)
        
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('user:cart')
        except Exception as e:
            logger.error(f"Order placement failed: {str(e)}")
            messages.error(request, 'An error occurred while placing the order.')
            return redirect('user:cart')
    
    return redirect('user:checkout')

@login_required
def esewa_verify(request):
    logger.debug(f"eSewa verify request GET params: {request.GET}")
    
    # Handle both direct query params and base64-encoded 'data' param
    order_id = request.GET.get('transaction_uuid')
    amt = request.GET.get('total_amount')
    ref_id = request.GET.get('transaction_id')
    data = None
    
    if not order_id and 'data' in request.GET:
        try:
            data = json.loads(base64.b64decode(request.GET['data']).decode('utf-8'))
            logger.debug(f"Decoded eSewa data: {data}")
            order_id = data.get('transaction_uuid')
            amt = data.get('total_amount')
            ref_id = data.get('transaction_code')
            # Verify callback signature
            signed_field_names = data.get('signed_field_names', '').split(',')
            signature_string = ','.join(f"{key}={data.get(key, '')}" for key in signed_field_names if key != 'signature')
            signature = hmac.new(
                key=settings.ESEWA_SECRET_KEY.encode('utf-8'),
                msg=signature_string.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            expected_signature = base64.b64encode(signature).decode('utf-8')
            if expected_signature != data.get('signature'):
                logger.error(f"Callback signature mismatch: expected={expected_signature}, received={data.get('signature')}")
                messages.error(request, 'Invalid payment signature.')
                return redirect('user:checkout')
        except (json.JSONDecodeError, base64.binascii.Error) as e:
            logger.error(f"Failed to decode data param: {str(e)}")
            messages.error(request, 'Invalid payment data.')
            return redirect('user:checkout')
    
    if not (order_id and amt and ref_id):
        logger.error(f"Missing required params: order_id={order_id}, amt={amt}, ref_id={ref_id}")
        messages.error(request, 'Invalid payment parameters.')
        return redirect('user:checkout')
    
    try:
        order = Order.objects.get(esewa_pid=order_id, user=request.user)
        if float(amt) != float(order.total_amount):
            logger.error(f"Amount mismatch: received={amt}, expected={order.total_amount}")
            messages.error(request, 'Invalid payment amount.')
            return redirect('user:checkout')
        
        # If callback data indicates success, attempt verification
        if data and data.get('status') == 'COMPLETE':
            try:
                # Verify payment with eSewa ePay-v2
                verification_url = "https://rc-epay.esewa.com.np/api/epay/transaction/status/"
                params = {
                    'product_code': settings.ESEWA_MERCHANT_ID,
                    'total_amount': str(order.total_amount),  # Ensure string format
                    'transaction_uuid': order.esewa_pid
                }
                # Generate signature for verification
                signature_string = f"total_amount={params['total_amount']},transaction_uuid={params['transaction_uuid']},product_code={params['product_code']}"
                signature = hmac.new(
                    key=settings.ESEWA_SECRET_KEY.encode('utf-8'),
                    msg=signature_string.encode('utf-8'),
                    digestmod=hashlib.sha256
                ).digest()
                headers = {'Signature': base64.b64encode(signature).decode('utf-8')}
                
                response = requests.get(verification_url, params=params, headers=headers)
                logger.debug(f"eSewa verification response: status={response.status_code}, text={response.text}")
                
                # Parse response as JSON
                try:
                    response_data = response.json()
                    response_status = response_data.get('status', '').upper()
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse verification response as JSON: {response.text}")
                    response_status = ''
                
                if response.status_code == 200 and response_status == 'COMPLETE':
                    order.status = 'accepted'
                    order.save()
                    Cart.objects.filter(user=request.user).delete()
                    messages.success(request, 'Payment successful! Order confirmed.')
                    return redirect('user:order_confirmation', order_id=order.id)
                else:
                    logger.error(f"Verification failed: status={response.status_code}, response={response.text}")
            except requests.RequestException as e:
                logger.error(f"eSewa verification request failed: {str(e)}")
                # Fallback: Accept payment if callback status is COMPLETE and signature is valid
                if data.get('status') == 'COMPLETE':
                    logger.warning(f"Fallback: Accepting payment based on callback status=COMPLETE")
                    order.status = 'accepted'
                    order.save()
                    Cart.objects.filter(user=request.user).delete()
                    messages.success(request, 'Payment successful! Order confirmed (fallback).')
                    return redirect('user:order_confirmation', order_id=order.id)
        
        order.status = 'canceled'
        order.save()
        logger.error(f"Payment verification failed: callback_status={data.get('status') if data else 'N/A'}")
        messages.error(request, 'Payment verification failed.')
        return redirect('user:checkout')
    except Order.DoesNotExist:
        logger.error(f"Order not found for esewa_pid={order_id}, user={request.user.email}")
        messages.error(request, 'Order not found.')
        return redirect('user:checkout')
    except Order.MultipleObjectsReturned:
        logger.error(f"Multiple orders found for esewa_pid={order_id}, user={request.user.email}")
        messages.error(request, 'Multiple orders found for this payment. Please contact support.')
        return redirect('user:checkout')

@login_required
def order_confirmation(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        cart_data = []
        for item in order.items.all():
            subtotal = item.quantity * item.price
            cart_data.append({
                'product': item.product,
                'quantity': item.quantity,
                'price': item.price,
                'subtotal': subtotal
            })
        return render(request, 'user/order_confirmation.html', {
            'order': order,
            'cart_data': cart_data,
            'total_amount': order.total_amount
        })
    except Order.DoesNotExist:
        raise Http404("Order not found")

@login_required
def add_review(request, product_id):
    if request.user.role != 'user':
        messages.error(request, 'Only users can add reviews.')
        return redirect('user:product_list')
    try:
        product = Product.objects.get(id=product_id)
        if request.method == 'POST':
            rating = int(request.POST.get('rating'))
            comment = request.POST.get('comment')
            Review.objects.create(
                user=request.user,
                product=product,
                rating=rating,
                comment=comment
            )
            messages.success(request, 'Review added successfully!')
            return redirect('user:product_list')
        return render(request, 'user/add_review.html', {'product': product})
    except Product.DoesNotExist:
        raise Http404("Product not found")