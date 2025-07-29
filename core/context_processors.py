from vendor.models import Category
from user.models import Cart, Wishlist

def cart_wishlist_counts(request):
    cart_count = Cart.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    wishlist_count = Wishlist.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
    }

def categories(request):
    return {
        'categories': Category.objects.all(),
    }