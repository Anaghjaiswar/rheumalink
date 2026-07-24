from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from rest_framework_simplejwt.tokens import RefreshToken
from user.models import User
from .forms import LoginForm


def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        if getattr(request.user, 'is_doctor', False):
            return redirect('doctor-dashboard')
        elif getattr(request.user, 'is_compounder', False):
            return redirect('compounder-dashboard')
        return redirect('clinic-home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(request, email=email, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(request, "This account is inactive. Please contact system administrator.")
                else:
                    login(request, user)
                    
                    # Generate SimpleJWT tokens for API access
                    refresh = RefreshToken.for_user(user)
                    access_token = str(refresh.access_token)
                    refresh_token = str(refresh)

                    # Determine target redirect URL
                    target = next_url
                    if not target:
                        if getattr(user, 'is_doctor', False) or user.role == User.Role.DOCTOR:
                            target = '/doctor-dashboard/'
                        elif getattr(user, 'is_compounder', False) or user.role == User.Role.COMPOUNDER:
                            target = '/compounder-dashboard/'
                        else:
                            target = '/'

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'success',
                            'redirect_url': target,
                            'access': access_token,
                            'refresh': refresh_token,
                            'user': {
                                'id': user.id,
                                'email': user.email,
                                'role': user.role,
                                'full_name': user.get_full_name() if hasattr(user, 'get_full_name') else user.email,
                            }
                        })

                    messages.success(request, f"Welcome back, {user.first_name or user.email}!")
                    response = redirect(target)
                    # Set JWT token in cookie for convenient API authorization
                    response.set_cookie('jwt_access', access_token, max_age=3600, httponly=False)
                    return response
            else:
                messages.error(request, "Invalid email or password. Please try again.")
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = LoginForm()

    context = {
        'form': form,
        'next': next_url,
    }
    return render(request, 'user/login.html', context)


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    response = redirect('login')
    response.delete_cookie('jwt_access')
    return response
