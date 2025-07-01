# Deploying to Azure with Secure Credential Handling

Based on the analysis of your Docker setup, here's a revised guide for deploying your application to Azure while securely handling the credentials in your `.env` file.

## Project Analysis

Your project is a FastAPI web application with:
- A production Docker setup using `Dockerfile.prod` and `docker-compose.prod.yaml`
- Nginx as a reverse proxy
- Sensitive credentials in the `.env` file (particularly a SendGrid API key)
- Email functionality that depends on these environment variables

## Recommended Azure Deployment Approach

### 1. Azure Container Apps (Recommended)

Azure Container Apps is ideal for your setup because it:
- Supports multi-container applications
- Integrates with GitHub for CI/CD
- Provides secure environment variable management
- Offers built-in scaling and HTTPS

### 2. Deployment Steps

#### Step 1: Prepare Your GitHub Repository

1. Ensure your `.env` file is in `.gitignore` (which it already is)
2. Push your code to GitHub if not already done

#### Step 2: Set Up Azure Container Registry (ACR)

```bash
# Login to Azure
az login

# Create a resource group if you don't have one
az group create --name sparrowrobotics-rg --location westus

# Create Azure Container Registry
az acr create --resource-group sparrowrobotics-rg --name sparrowroboticsacr --sku Basic

# Enable admin user for the registry
az acr update --name sparrowroboticsacr --admin-enabled true
```

#### Step 3: Register Required Resource Providers

Before creating the Container App Environment, you need to ensure all required resource providers are registered with your Azure subscription:

```bash
# Register the Microsoft.OperationalInsights provider
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.KeyVault --wait
```

This step is necessary because Azure Container Apps uses Azure Log Analytics (part of the Microsoft.OperationalInsights namespace) for logging and monitoring. The `--wait` flag ensures the command doesn't return until the registration is complete, which may take a few minutes.

#### Step 4: Create Azure Container App Environment

```bash
# Create Container App Environment
az containerapp env create \
  --name sparrowrobotics-env \
  --resource-group sparrowrobotics-rg \
  --location westus
```

#### Step 5: Secure Credential Management with Azure Key Vault

For secure handling of credentials, use Azure Key Vault:

```bash
# Create a Key Vault
az keyvault create --name sparrowrobotics-kv --resource-group sparrowrobotics-rg --location westus

# Store your secrets securely in environment variables first (don't echo them)
# DO NOT include actual values in scripts or CI/CD pipelines
export MAIL_USERNAME="your-username"
export MAIL_PASSWORD="your-password"
export MAIL_TO="your-recipient-email"
export MAIL_FROM="your-sender-email"



# Give your user role as a kv officer
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
az role assignment create  \
 --assignee $USER_OBJECT_ID   \
 --role "Key Vault Secrets Officer"  \
 --scope $(az keyvault show --name sparrowrobotics-kv --query id -o tsv)


# Add your secrets to Key Vault (values come from environment variables)
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-USERNAME" --value "$MAIL_USERNAME"
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-PASSWORD" --value "$MAIL_PASSWORD"
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-TO" --value "$MAIL_TO"
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-FROM" --value "$MAIL_FROM"
```

#### Step 6: Build and Deploy Your Application

```bash
# Build and push your Docker image to ACR
az acr build --registry sparrowroboticsacr --image sparrowrobotics:latest .

# Create the Container App with managed identity
az containerapp create \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --environment sparrowrobotics-env \
  --registry-server sparrowroboticsacr.azurecr.io \
  --image sparrowroboticsacr.azurecr.io/sparrowrobotics:latest \
  --target-port 80 \
  --ingress external \
  --system-assigned

# Get the principal ID of the Container App
principalId=$(az containerapp identity show --name sparrowrobotics --resource-group sparrowrobotics-rg --query principalId -o tsv)

# Grant the Container App access to Key Vault secrets
az role assignment create \
  --assignee $principalId \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name sparrowrobotics-kv --query id -o tsv)
```

#### Step 7: Configure Environment Variables in Container App

```bash
# Configure the Container App to use Key Vault references
az containerapp secret set \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --secrets \
    mail-username=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-USERNAME,identityref:system \
    mail-password=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-PASSWORD,identityref:system \
    mail-to=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-TO,identityref:system \
    mail-from=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-FROM,identityref:system

# Set environment variables that reference the secrets
az containerapp update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --set-env-vars \
    MAIL_USERNAME=secretref:mail-username \
    MAIL_PASSWORD=secretref:mail-password \
    MAIL_TO=secretref:mail-to \
    MAIL_FROM=secretref:mail-from
```

### 3. Setting Up GitHub Actions for CI/CD

Create a `.github/workflows/azure-deploy.yml` file:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Log in to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Build and push image to ACR
      uses: azure/docker-login@v1
      with:
        login-server: sparrowroboticsacr.azurecr.io
        username: ${{ secrets.ACR_USERNAME }}
        password: ${{ secrets.ACR_PASSWORD }}
    
    - run: |
        docker build -f Dockerfile.prod -t sparrowroboticsacr.azurecr.io/sparrowrobotics:${{ github.sha }} .
        docker push sparrowroboticsacr.azurecr.io/sparrowrobotics:${{ github.sha }}
    
    - name: Deploy to Azure Container Apps
      uses: azure/containerapp-deploy@v1
      with:
        resource-group: sparrowrobotics-rg
        name: sparrowrobotics
        image: sparrowroboticsacr.azurecr.io/sparrowrobotics:${{ github.sha }}
```

To set up the GitHub secrets:

1. Create a service principal:
```bash
az ad sp create-for-rbac --name "sparrowrobotics-github" 
--role contributor \
  --scopes /subscriptions/5a3935a9-d61b-444f-a13f-194cd9bd49ad/resourceGroups/sparrowrobotics-rg \
  --sdk-auth
  
```

2. Add the result JSON output as a GitHub secret (via GUI) named `AZURE_CREDENTIALS`

3. Add ACR credentials as secrets:
```bash
ACR_USERNAME=$(az acr credential show -n sparrowroboticsacr --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show -n sparrowroboticsacr --query "passwords[0].value" -o tsv)
```

4. Add these as GitHub secrets `ACR_USERNAME` and `ACR_PASSWORD`

## Additional Considerations

1. **Multi-container setup**: For your Nginx + web app setup, you'll need to:
   - Create a Docker Compose file for Azure Container Apps
   - Or use separate Container Apps with networking between them

2. **Custom domain**: Set up a custom domain in Azure Container Apps:
```bash
az containerapp hostname add --name sparrowrobotics --resource-group sparrowrobotics-rg --hostname www.sparrowrobotics.ca
```

3. **Monitoring**: Enable Application Insights for monitoring:
```bash
az monitor app-insights component create --app sparrowrobotics --location westus --resource-group sparrowrobotics-rg
```

This approach ensures your credentials are securely stored in Azure Key Vault and injected into your application without being exposed in your code, GitHub repository, or Docker images.