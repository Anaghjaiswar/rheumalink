from django import forms
from django.utils.translation import gettext_lazy as _

class LoginForm(forms.Form):
    email = forms.EmailField(
        label=_("Email Address"),
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@clinic.com',
            'class': 'form-control',
            'autocomplete': 'email',
            'required': True,
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••',
            'class': 'form-control',
            'autocomplete': 'current-password',
            'required': True,
        })
    )
