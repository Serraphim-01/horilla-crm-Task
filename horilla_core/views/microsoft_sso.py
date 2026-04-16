"""
Microsoft SSO Views

This module contains views for handling Microsoft Single Sign-On (SSO) authentication flow.
"""

import logging
import uuid

import msal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

logger = logging.getLogger(__name__)


def get_msal_app(request=None):
    """
    Get or create MSAL application instance using database settings.
    
    Args:
        request: HTTP request object (optional, for building redirect URI)
        
    Returns:
        Tuple of (msal.ConfidentialClientApplication instance, MicrosoftSSOSettings) or (None, None)
    """
    from horilla_core.models import MicrosoftSSOSettings
    
    # Load settings from database
    sso_settings = MicrosoftSSOSettings.load()
    
    # Check if SSO is enabled
    if not sso_settings.is_enabled:
        logger.warning("Microsoft SSO is not enabled")
        return None, None
    
    # Get credentials from settings
    client_id = sso_settings.client_id
    client_secret = sso_settings.get_client_secret()
    tenant_id = sso_settings.tenant_id or 'common'
    
    if not client_id or not client_secret:
        logger.error("Microsoft SSO credentials not configured")
        return None, None
    
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    msal_app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )
    
    return msal_app, sso_settings


class MicrosoftSSOLoginView(View):
    """
    View to initiate Microsoft SSO login flow.
    
    This view redirects the user to Microsoft's login page.
    """
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Initiate the Microsoft SSO OAuth flow.
        
        Args:
            request: The HTTP request object
            
        Returns:
            Redirect response to Microsoft login page
        """
        try:
            msal_app, sso_settings = get_msal_app(request)
            
            if msal_app is None:
                messages.error(request, "Microsoft SSO is not configured or enabled.")
                return redirect('horilla_core:login')
            
            # Generate a unique state for CSRF protection
            state = str(uuid.uuid4())
            request.session['microsoft_sso_state'] = state
            
            # Generate a unique nonce for token validation
            nonce = str(uuid.uuid4())
            request.session['microsoft_sso_nonce'] = nonce
            
            # Create the authorization flow
            auth_url = msal_app.get_authorization_request_url(
                scopes=sso_settings.get_scopes_list(),
                redirect_uri=request.build_absolute_uri(
                    reverse('horilla_core:microsoft_sso_callback')
                ),
                state=state,
                nonce=nonce,
                prompt='select_account',  # Allow user to select account
            )
            
            return redirect(auth_url)
            
        except Exception as e:
            logger.error(f"Error initiating Microsoft SSO login: {str(e)}", exc_info=True)
            messages.error(request, "Unable to initiate Microsoft login. Please try again.")
            return redirect('horilla_core:login')


class MicrosoftSSOCallbackView(View):
    """
    View to handle the callback from Microsoft after authentication.
    
    This view processes the authorization code and completes the login flow.
    """
    
    def get(self, request: HttpRequest) -> HttpResponse:
        """
        Handle the OAuth callback from Microsoft.
        
        Args:
            request: The HTTP request object
            
        Returns:
            Redirect response to home page or login page
        """
        try:
            # Get the authorization code from the callback
            code = request.GET.get('code')
            state = request.GET.get('state')
            
            if not code:
                error = request.GET.get('error', 'Unknown error')
                error_description = request.GET.get('error_description', '')
                logger.error(f"Microsoft SSO error: {error} - {error_description}")
                messages.error(request, f"Microsoft login failed: {error}")
                return redirect('horilla_core:login')
            
            # Validate state for CSRF protection
            session_state = request.session.get('microsoft_sso_state')
            if state != session_state:
                logger.warning("Microsoft SSO state mismatch - possible CSRF attack")
                messages.error(request, "Authentication failed. Please try again.")
                return redirect('horilla_core:login')
            
            # Clear the state from session
            del request.session['microsoft_sso_state']
            
            # Exchange the authorization code for tokens
            msal_app, sso_settings = get_msal_app(request)
            
            if msal_app is None:
                messages.error(request, "Microsoft SSO is not configured or enabled.")
                return redirect('horilla_core:login')
            
            token_response = msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=sso_settings.get_scopes_list(),
                redirect_uri=request.build_absolute_uri(
                    reverse('horilla_core:microsoft_sso_callback')
                ),
            )
            
            # Check for errors in token response
            if 'error' in token_response:
                error = token_response.get('error')
                error_description = token_response.get('error_description', '')
                logger.error(f"Microsoft token acquisition error: {error} - {error_description}")
                messages.error(request, f"Microsoft login failed: {error}")
                return redirect('horilla_core:login')
            
            # Extract ID token claims for user information
            if 'id_token_claims' not in token_response:
                logger.error("No ID token claims in Microsoft response")
                messages.error(request, "Microsoft login failed. Please try again.")
                return redirect('horilla_core:login')
            
            # Authenticate the user using our custom backend
            from horilla_core.auth.microsoft_sso import MicrosoftSSOBackend
            
            backend = MicrosoftSSOBackend()
            user = backend.authenticate(
                request=request, 
                token_response=token_response
            )
            
            if user is None:
                messages.error(
                    request, 
                    "Authentication failed. Your Microsoft account may not be authorized."
                )
                return redirect('horilla_core:login')
            
            # Check if user's email domain is allowed
            if not sso_settings.is_domain_allowed(user.email):
                logger.warning(f"User domain not allowed: {user.email}")
                messages.error(
                    request,
                    "Your email domain is not allowed to access this application."
                )
                user.delete()  # Remove auto-created user if domain not allowed
                return redirect('horilla_core:login')
            
            # Log the user in
            login(request, user, backend='horilla_core.auth.microsoft_sso.MicrosoftSSOBackend')
            messages.success(request, "Successfully logged in with Microsoft!")
            
            # Redirect to the next URL or home page
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
            
        except Exception as e:
            logger.error(f"Error in Microsoft SSO callback: {str(e)}", exc_info=True)
            messages.error(request, "An error occurred during Microsoft login. Please try again.")
            return redirect('horilla_core:login')
