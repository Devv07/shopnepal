from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'gender', 'role', 'password1', 'password2']
        widgets = {
            'role': forms.Select(choices=[('user', 'User'), ('vendor', 'Vendor')]),
            'gender': forms.Select(choices=CustomUser.GENDER_CHOICES),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g., +9771234567890'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and CustomUser.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already registered.")
        return phone_number