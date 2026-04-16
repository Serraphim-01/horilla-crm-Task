"""
Microsoft SSO Authentication Backend

This module provides a custom authentication backend for Microsoft Single Sign-On (SSO)
using the Microsoft Authentication Library (MSAL).
"""

import logging

import msal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

logger = logging.getLogger(__name__)

User = get_user_model()


class MicrosoftSSOBackend(BaseBackend):
    """
    Custom authentication backend for Microsoft SSO.
    
    This backend validates Microsoft identity tokens and authenticates users
    based on their Microsoft organizational account (Entra ID / Azure AD).
    """

    def authenticate(self, request, token_response=None, **kwargs):
        """
        Authenticate a user using Microsoft SSO token response.
        
        Args:
            request: The HTTP request object
            token_response: The token response from Microsoft after OAuth flow
            
        Returns:
            User object if authentication is successful, None otherwise
        """
        if token_response is None or 'error' in token_response:
            if token_response and 'error' in token_response:
                logger.error(f"Microsoft SSO error: {token_response.get('error')}")
            return None

        try:
            # Extract user information from token
            id_token_claims = token_response.get('id_token_claims', {})
            
            # Get email and other user details from the token
            email = (
                id_token_claims.get('email') or 
                id_token_claims.get('preferred_username') or 
                id_token_claims.get('upn') or
                token_response.get('id_token_claims', {}).get('email')
            )
            
            if not email:
                logger.error("No email found in Microsoft token")
                return None

            # Extract user details
            first_name = id_token_claims.get('given_name', '')
            last_name = id_token_claims.get('family_name', '')
            display_name = id_token_claims.get('name', '')
            
            # If we have display name but no first/last, split it
            if display_name and not first_name and not last_name:
                name_parts = display_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Try to find existing user or create new one
            user = self._get_or_create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                token_response=token_response
            )

            return user

        except Exception as e:
            logger.error(f"Error during Microsoft SSO authentication: {str(e)}", exc_info=True)
            return None

    def _get_or_create_user(self, email, first_name, last_name, token_response):
        """
        Get existing user or create a new one based on Microsoft SSO data.
        
        Args:
            email: User's email address from Microsoft
            first_name: User's first name
            last_name: User's last name
            token_response: Full token response from Microsoft
            
        Returns:
            User object
        """
        try:
            # Try to find user by email
            user = User.objects.get(email=email)
            
            # Update user information if needed
            if not user.first_name and first_name:
                user.first_name = first_name
            if not user.last_name and last_name:
                user.last_name = last_name
                
            # Ensure user is active
            if not user.is_active:
                logger.warning(f"Inactive user attempted Microsoft SSO login: {email}")
                return None
                
            user.save()
            logger.info(f"User authenticated via Microsoft SSO: {email}")
            return user

        except User.DoesNotExist:
            # Check if auto-provisioning is enabled
            if not getattr(settings, 'MICROSOFT_SSO_AUTO_PROVISION', True):
                logger.warning(f"User not found and auto-provisioning disabled: {email}")
                return None

            # Create new user
            username = email.split('@')[0]
            
            # Ensure username is unique
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )

            # Set unusable password since user will login via SSO
            user.set_unusable_password()
            user.save()

            logger.info(f"New user created via Microsoft SSO: {email}")
            return user

    def get_user(self, user_id):
        """
        Get user by ID.
        
        Args:
            user_id: The user's primary key
            
        Returns:
            User object or None
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
