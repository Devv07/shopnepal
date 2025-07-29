from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from .forms import CustomUserCreationForm
from django.contrib import messages
from user.models import Cart, Wishlist
from .models import NewsletterSubscription

def home(request):
    from vendor.models import Category, Product
    categories = Category.objects.all()[:6]
    products = Product.objects.all().order_by('-created_at')[:8]
    return render(request, 'user/home.html', {
        'categories': categories,
        'products': products,
    })

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Specify the authentication backend for login
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Registration successful! Welcome to Shop Nepal.')
            return redirect('user:dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)  # no need to manually pass backend here
            if user.role == 'vendor':
                if user.is_verified:
                    return redirect('vendor:dashboard')
                messages.error(request, 'Your vendor account is not yet verified.')
                return redirect('core:home')
            return redirect('user:dashboard')
        messages.error(request, 'Invalid email or password.')

    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('core:home')

def faq(request):
    return render(request, 'core/faq.html')

def shipping_info(request):
    return render(request, 'core/shipping_info.html')

def returns(request):
    return render(request, 'core/returns.html')

def contact(request):
    return render(request, 'core/contact.html')

def newsletter(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            NewsletterSubscription.objects.get_or_create(email=email)
            messages.success(request, 'Subscribed to newsletter!')
        else:
            messages.error(request, 'Please provide a valid email.')
        return redirect('core:home')
    return redirect('core:home')