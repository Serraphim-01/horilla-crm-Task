# Microsoft SSO Setup Guide - Admin Configuration

This guide explains how to configure Microsoft Single Sign-On (SSO) through the Horilla CRM admin interface.

## Overview

Microsoft SSO allows users to log in to Horilla CRM using their Microsoft organizational credentials (Azure AD / Microsoft Entra ID). All configuration is now managed through the admin settings panel with encrypted storage of sensitive credentials.

## Features

✅ **Admin Panel Configuration** - Configure SSO through the web interface  
✅ **Encrypted Storage** - Client secrets are encrypted before storing in database  
✅ **Auto-Provisioning** - Automatically create users on first login (optional)  
✅ **Domain Restrictions** - Limit access to specific email domains  
✅ **Custom Scopes** - Configure Microsoft Graph API permissions  
✅ **Customizable Button** - Change the login button text  

## Step 1: Register Application in Azure AD

### 1.1 Navigate to Azure Portal
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** (formerly Azure Active Directory)
3. Click on **App registrations** in the left menu
4. Click **New registration**

### 1.2 Configure Application Registration
Fill in the following details:

- **Name**: `Horilla CRM` (or your preferred name)
- **Supported account types**: Choose one:
  - `Accounts in this organizational directory only` - Single tenant (recommended)
  - `Accounts in any organizational directory` - Multi-tenant
- **Redirect URI**: 
  - Type: `Web`
  - URL: `http://localhost:8000/microsoft-sso/callback/` (development)
  - Production: `https://yourdomain.com/microsoft-sso/callback/`

Click **Register**.

### 1.3 Copy Application IDs
After registration, copy these values:
- **Application (client) ID** - You'll need this for the Client ID field
- **Directory (tenant) ID** - You'll need this for the Tenant ID field (or use `common` for multi-tenant)

### 1.4 Create Client Secret
1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Add a description (e.g., "Horilla CRM SSO")
4. Choose an expiration period
5. Click **Add**
6. **IMPORTANT**: Copy the secret value immediately - you won't see it again!

### 1.5 Configure API Permissions
1. Go to **API permissions** in your app registration
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions**
5. Add these permissions:
   - `User.Read` - Sign in and read user profile
   - `email` - View user email address
   - `profile` - View user profile
   - `openid` - Sign users in
6. Click **Add permissions**
7. Click **Grant admin consent** (for single-tenant apps)

## Step 2: Configure Microsoft SSO in Horilla CRM

### 2.1 Access Microsoft SSO Settings
1. Log in to Horilla CRM as an administrator
2. Navigate to **Settings** (gear icon)
3. In the left sidebar, under **General**, click **Microsoft SSO**
4. You'll see the Microsoft SSO configuration page

### 2.2 Fill in Configuration Details

#### Azure AD Configuration
- **Enable Microsoft SSO**: Check this box to enable SSO
- **Client ID**: Paste the Application (client) ID from Azure AD
- **Client Secret**: Paste the client secret you created (will be encrypted automatically)
- **Tenant ID**: 
  - For single-tenant: Paste your Directory (tenant) ID
  - For multi-tenant: Enter `common` or `organizations`

#### User Management
- **Auto-provision Users**: 
  - ✅ Enabled: New users are automatically created on first login
  - ❌ Disabled: Only pre-existing users can login via SSO
- **Allowed Email Domains**: 
  - Leave empty to allow all domains
  - Enter comma-separated domains to restrict access (e.g., `company.com,partner.org`)

#### Advanced Settings
- **OAuth Scopes**: Comma-separated list of Microsoft Graph permissions (default: `User.Read,email,profile,openid`)
- **Button Text**: Custom text for the login button (default: "Sign in with Microsoft")

### 2.3 Save Settings
Click **Save Settings** at the bottom of the page. Your credentials will be encrypted and stored securely in the database.

## Step 3: Test the Integration

### 3.1 Verify Configuration
1. After saving, you should see the status change to **Enabled** (green badge)
2. Log out of the admin panel

### 3.2 Test Login
1. Go to the login page: `http://localhost:8000/login/`
2. You should see a **"Sign in with Microsoft"** button below the login form
3. Click the button
4. You'll be redirected to Microsoft's login page
5. Sign in with your Microsoft work account
6. After successful authentication, you'll be redirected back to Horilla CRM

### 3.3 Verify User Creation
If auto-provisioning is enabled:
1. Log in as an admin
2. Navigate to **Settings → Users**
3. You should see the new user created with their Microsoft account information

## Configuration Options Explained

### Enable Microsoft SSO
Turns the SSO feature on or off without deleting your configuration.

### Client ID
The unique identifier for your Azure AD application registration.

### Client Secret
The secret key for your application. This is **encrypted** before being stored in the database.

### Tenant ID
- **Single-tenant**: Your specific Azure AD tenant ID (more secure)
- **Multi-tenant**: Use `common` to allow any Microsoft account

### Auto-provision Users
- **Enabled**: Automatically creates user accounts on first Microsoft login
- **Disabled**: Only allows login for users that already exist in Horilla CRM

### Allowed Email Domains
Restrict SSO access to specific email domains:
- Empty: All Microsoft accounts can login
- `company.com`: Only users with @company.com emails
- `company.com,partner.org`: Multiple domains allowed

### OAuth Scopes
Microsoft Graph API permissions requested during authentication:
- `User.Read` - Basic profile information
- `email` - User's email address
- `profile` - User's profile details
- `openid` - OpenID Connect authentication

### Button Text
Customize the text displayed on the Microsoft login button.

## Security Features

### Encrypted Storage
- Client secrets are encrypted using Fernet symmetric encryption
- Encryption key is stored in `.encryption_key` file
- Secrets are never displayed in the admin interface after saving

### Domain Validation
- Email domains are validated during login
- Users with non-allowed domains are rejected
- Auto-created users are deleted if domain is not allowed

### CSRF Protection
- State parameter validation prevents CSRF attacks
- Nonce validation ensures token integrity

### Admin-Only Access
- Only superusers can access SSO settings
- Permission check: `horilla_core.can_manage_microsoft_sso`

## Troubleshooting

### SSO Button Not Showing
**Problem**: Microsoft SSO button doesn't appear on login page  
**Solution**: 
1. Go to Settings → Microsoft SSO
2. Ensure "Enable Microsoft SSO" is checked
3. Verify Client ID and Client Secret are filled
4. Click Save Settings

### Login Fails with "Not Configured"
**Problem**: Error message "Microsoft SSO is not configured or enabled"  
**Solution**:
1. Check that SSO is enabled in settings
2. Verify Client ID is not empty
3. Verify Client Secret is not empty
4. Check Tenant ID is valid

### Client Secret Issues
**Problem**: Authentication fails after saving  
**Solution**:
1. The client secret field shows as empty after saving (this is normal for security)
2. If you need to update it, enter the new secret and save
3. Leave it blank to keep the existing secret

### Domain Restriction Problems
**Problem**: User cannot login due to domain restriction  
**Solution**:
1. Check the user's email domain
2. Go to Microsoft SSO settings
3. Add the domain to "Allowed Email Domains"
4. Save settings

### Azure AD Errors
**Problem**: Microsoft login page shows errors  
**Solutions**:
- `invalid_client`: Check Client ID and Client Secret
- `redirect_uri_mismatch`: Verify redirect URI in Azure AD matches `/microsoft-sso/callback/`
- `unauthorized_client`: Ensure API permissions are granted

## Updating Azure AD Configuration

### Change Redirect URI
If your domain changes:
1. Go to Azure Portal → App registrations → Your app
2. Click **Authentication**
3. Update the redirect URI to: `https://yourdomain.com/microsoft-sso/callback/`

### Add More Permissions
1. Go to **API permissions**
2. Click **Add a permission**
3. Select required permissions
4. Click **Grant admin consent**

## Migration from Environment Variables

If you previously used environment variables for SSO configuration:

1. The old environment variables are now ignored:
   - `MICROSOFT_SSO_ENABLED`
   - `MICROSOFT_SSO_CLIENT_ID`
   - `MICROSOFT_SSO_CLIENT_SECRET`
   - `MICROSOFT_SSO_TENANT_ID`

2. Migrate your settings:
   - Go to Settings → Microsoft SSO
   - Enter all configuration values
   - Click Save Settings

3. Remove the old environment variables from your `.env` file (optional)

## Best Practices

1. **Use Single-Tenant**: For production, use your specific tenant ID instead of `common`
2. **Enable Domain Restrictions**: Limit access to your organization's domain
3. **Regular Secret Rotation**: Update client secret before expiration
4. **Monitor Logs**: Check application logs for authentication failures
5. **Test in Staging**: Test SSO configuration in a staging environment first
6. **Backup Settings**: Document your Azure AD configuration separately

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Azure AD app registration configuration
3. Check application logs for detailed error messages
4. Verify all required API permissions are granted

## Additional Resources

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [MSAL Python Documentation](https://github.com/AzureAD/microsoft-authentication-library-for-python)
- [Azure AD App Registration Guide](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
