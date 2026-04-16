# Microsoft SSO Setup Guide for Horilla CRM

This guide will walk you through setting up Single Sign-On (SSO) with Microsoft Work Accounts (Azure AD / Microsoft Entra ID) for your Horilla CRM application.

## Overview

Microsoft SSO allows users to log in to Horilla CRM using their Microsoft organizational credentials. When a user clicks "Sign in with Microsoft", they are redirected to Microsoft's login page. After successful authentication, they are automatically logged into Horilla CRM. If the user doesn't exist in Horilla CRM, they can be automatically created (auto-provisioning).

## Prerequisites

1. A Microsoft Azure account with access to Azure Active Directory (Entra ID)
2. Administrator permissions to register applications in Azure AD
3. Horilla CRM installed and running

## Step 1: Register Application in Azure AD

### 1.1 Navigate to Azure Portal
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** (or **Microsoft Entra ID**)
3. Click on **App registrations** in the left menu
4. Click **New registration**

### 1.2 Configure Application Registration
Fill in the following details:

- **Name**: `Horilla CRM` (or your preferred name)
- **Supported account types**: Choose one:
  - `Accounts in this organizational directory only` - Single tenant (recommended for most organizations)
  - `Accounts in any organizational directory` - Multi-tenant
- **Redirect URI**: 
  - Type: `Web`
  - URL: `http://localhost:8000/microsoft-sso/callback/` (for development)
  - For production: `https://yourdomain.com/microsoft-sso/callback/`

Click **Register**.

### 1.3 Note Down Application IDs
After registration, you'll see:
- **Application (client) ID**: Copy this value
- **Directory (tenant) ID**: Copy this value (if using single-tenant)

### 1.4 Create Client Secret
1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Add a description (e.g., "Horilla CRM SSO")
4. Choose an expiration period
5. Click **Add**
6. **IMPORTANT**: Copy the secret value immediately - you won't be able to see it again!

### 1.5 Configure API Permissions
1. Go to **API permissions** in your app registration
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions**
5. Add the following permissions:
   - `User.Read` - Sign in and read user profile
   - `email` - View user email address
   - `profile` - View user profile
   - `openid` - Sign users in
6. Click **Add permissions**
7. If using single-tenant, click **Grant admin consent** for your organization

### 1.6 Configure Token Configuration (Optional but Recommended)
1. Go to **Token configuration**
2. Click **Add optional token claim**
3. Select **ID** token type
4. Add these claims:
   - `email`
   - `upn` (User Principal Name)
5. Click **Add**

## Step 2: Configure Horilla CRM

### 2.1 Install Required Package
The `msal` package has been added to requirements.txt. Install it:

```bash
pip install msal==1.31.0
```

Or reinstall all requirements:

```bash
pip install -r requirements.txt
```

### 2.2 Update Environment Variables
Add the following to your `.env` file:

```env
# Microsoft SSO Configuration
MICROSOFT_SSO_ENABLED=True
MICROSOFT_SSO_CLIENT_ID=your_client_id_here
MICROSOFT_SSO_CLIENT_SECRET=your_client_secret_here
MICROSOFT_SSO_TENANT_ID=your_tenant_id_here
MICROSOFT_SSO_AUTO_PROVISION=True
```

**Configuration Options:**

- `MICROSOFT_SSO_ENABLED`: Set to `True` to enable Microsoft SSO
- `MICROSOFT_SSO_CLIENT_ID`: The Application (client) ID from Azure AD
- `MICROSOFT_SSO_CLIENT_SECRET`: The client secret you created
- `MICROSOFT_SSO_TENANT_ID`: 
  - For single-tenant: Use your Directory (tenant) ID
  - For multi-tenant: Use `common` or `organizations`
- `MICROSOFT_SSO_AUTO_PROVISION`: 
  - `True`: Automatically create user accounts on first login
  - `False`: Only allow pre-existing users to login via SSO

### 2.3 Update Redirect URI for Production
In Azure AD, update the redirect URI to match your production URL:
- Development: `http://localhost:8000/microsoft-sso/callback/`
- Production: `https://yourdomain.com/microsoft-sso/callback/`

## Step 3: Test the Integration

### 3.1 Restart Your Application
```bash
python manage.py runserver
```

### 3.2 Test Login
1. Navigate to the login page: `http://localhost:8000/login/`
2. You should see a "Sign in with Microsoft" button below the login form
3. Click the button
4. You'll be redirected to Microsoft's login page
5. Sign in with your Microsoft work account
6. After successful authentication, you'll be redirected back to Horilla CRM

### 3.3 Verify User Creation (if auto-provisioning is enabled)
1. Log in as an admin
2. Navigate to Users section
3. You should see the new user created with their Microsoft account information

## Step 4: User Management

### Auto-Provisioning Behavior
When `MICROSOFT_SSO_AUTO_PROVISION=True`:
- New users are automatically created on first login
- Username is derived from email (part before @)
- First name, last name, and email are populated from Microsoft
- Password is set as unusable (user must use SSO to login)
- User is marked as active

### Pre-existing Users
If a user already exists in Horilla CRM with the same email:
- Their account will be linked to Microsoft SSO
- Existing permissions and roles are preserved
- User can login with either SSO or password (if password is set)

### Disabling Auto-Provisioning
Set `MICROSOFT_SSO_AUTO_PROVISION=False` to:
- Only allow pre-existing users to login via SSO
- Prevent automatic account creation
- Require admin to manually create user accounts first

## Troubleshooting

### Common Issues

#### 1. "Microsoft login failed: invalid_client"
- **Cause**: Incorrect client ID or secret
- **Solution**: Verify your credentials in Azure AD and .env file

#### 2. "Microsoft login failed: redirect_uri mismatch"
- **Cause**: Redirect URI doesn't match Azure AD configuration
- **Solution**: Update redirect URI in Azure App Registration to match your URL

#### 3. "Authentication failed. Your Microsoft account may not be authorized"
- **Cause**: User not found and auto-provisioning disabled
- **Solution**: Enable auto-provisioning or manually create the user

#### 4. "No email found in Microsoft token"
- **Cause**: Missing email permissions or claims
- **Solution**: Ensure `email` and `User.Read` permissions are added in Azure AD

#### 5. SSO button not showing on login page
- **Cause**: `MICROSOFT_SSO_ENABLED` is False or not set
- **Solution**: Set `MICROSOFT_SSO_ENABLED=True` in your .env file

### Enable Debug Logging
Add this to your settings to debug SSO issues:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'horilla_core.auth.microsoft_sso': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'horilla_core.views.microsoft_sso': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Security Considerations

1. **Client Secret**: Store securely in environment variables, never in code
2. **HTTPS**: Use HTTPS in production for the callback URL
3. **Tenant ID**: Use your specific tenant ID for single-tenant apps (more secure than `common`)
4. **Auto-provisioning**: Consider disabling in production if you want to control user creation
5. **Permissions**: Only request the minimum permissions needed
6. **Token Validation**: MSAL library handles token validation automatically

## Advanced Configuration

### Custom Scopes
If you need additional Microsoft Graph API permissions:

```python
MICROSOFT_SSO_SCOPES = [
    'User.Read',
    'email',
    'profile',
    'openid',
    # Add more scopes as needed
]
```

### Custom User Creation Logic
You can customize the user creation logic by modifying the `_get_or_create_user` method in `horilla_core/auth/microsoft_sso.py`.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Azure AD app registration configuration
3. Verify environment variables are set correctly
4. Check application logs for error messages

## Additional Resources

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [MSAL Python Documentation](https://github.com/AzureAD/microsoft-authentication-library-for-python)
- [Azure AD App Registration Guide](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
