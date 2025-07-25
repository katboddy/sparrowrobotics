
# Deploying to Azure with Secure Credential Handling

This guide describes the current state of the deployment for your FastAPI web application to Azure Container Apps, with secure credential handling using Azure Key Vault.

## Project Analysis

Your project is a FastAPI web application with:
- A production Docker setup using `Dockerfile.prod` and `docker-compose.prod.yaml`
- Sensitive credentials in the `.env` file (particularly a SendGrid API key)
- Email functionality that depends on these environment variables

## Current Deployment Architecture

The application is currently deployed as a **single-container setup** directly exposing the FastAPI application:

- **Container Name**: sparrowrobotics
- **Image**: sparrowroboticsacr.azurecr.io/sparrowrobotics-web:latest
- **Exposed Port**: 8000
- **Credentials**: Securely stored in Azure Key Vault and injected as environment variables

## Deployment Steps

### Step 1: Prepare Your GitHub Repository

1. Ensure your `.env` file is in `.gitignore` (which it already is)
2. Push your code to GitHub if not already done

### Step 2: Set Up Azure Container Registry (ACR)

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

### Step 3: Register Required Resource Providers

Before creating the Container App Environment, you need to ensure all required resource providers are registered with your Azure subscription:

```bash
# Register the Microsoft.OperationalInsights provider
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.KeyVault --wait
```

This step is necessary because Azure Container Apps uses Azure Log Analytics (part of the Microsoft.OperationalInsights namespace) for logging and monitoring. The `--wait` flag ensures the command doesn't return until the registration is complete, which may take a few minutes.

### Step 4: Create Azure Container App Environment

```bash
# Create Container App Environment
az containerapp env create \
  --name sparrowrobotics-env \
  --resource-group sparrowrobotics-rg \
  --location westus
```

### Step 5: Secure Credential Management with Azure Key Vault

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
az role assignment create \
 --assignee $USER_OBJECT_ID \
 --role "Key Vault Secrets Officer" \
 --scope $(az keyvault show --name sparrowrobotics-kv --query id -o tsv)

# Add your secrets to Key Vault (values come from environment variables)
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-USERNAME" --value "$MAIL_USERNAME"
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-PASSWORD" --value "$MAIL_PASSWORD"
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-TO" --value "$MAIL_TO"
az keyvault secret set --vault-name sparrowrobotics-kv --name "MAIL-FROM" --value "$MAIL_FROM"
```

### Step 6: Build and Push the Web Application Image to ACR

```bash
# Build and push the web application image
az acr build --registry sparrowroboticsacr --image sparrowrobotics-web:latest --file Dockerfile.prod .
```

### Step 7: Deploy the Single-Container Application

```bash
# Create the Container App with managed identity
az containerapp create \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --environment sparrowrobotics-env \
  --registry-server sparrowroboticsacr.azurecr.io \
  --registry-username sparrowroboticsacr \
  --registry-password $(az acr credential show -n sparrowroboticsacr --query "passwords[0].value" -o tsv) \
  --image sparrowroboticsacr.azurecr.io/sparrowrobotics-web:latest \
  --ingress external \
  --target-port 8000 \
  --system-assigned

# Get the principal ID of the Container App
principalId=$(az containerapp identity show --name sparrowrobotics --resource-group sparrowrobotics-rg --query principalId -o tsv)

# Grant the Container App access to Key Vault secrets
az role assignment create \
  --assignee $principalId \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name sparrowrobotics-kv --query id -o tsv)
```

### Step 8: Configure Environment Variables in Container App

```bash
# Configure the secrets for the container
az containerapp secret set \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --secrets \
    mail-username=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-USERNAME,identityref:system \
    mail-password=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-PASSWORD,identityref:system \
    mail-to=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-TO,identityref:system \
    mail-from=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-FROM,identityref:system

# Set environment variables for the container
az containerapp update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --container-name sparrowrobotics \
  --set-env-vars \
    MAIL_USERNAME=secretref:mail-username \
    MAIL_PASSWORD=secretref:mail-password \
    MAIL_TO=secretref:mail-to \
    MAIL_FROM=secretref:mail-from
```

## Custom Domain Configuration with NameCheap

After deploying your application, you'll need to configure your custom domain from NameCheap. Here are the detailed steps:

#### Step 1: Get Your Azure Container App's Default Domain

```bash
# Get the default domain of your Container App
az containerapp show --name sparrowrobotics --resource-group sparrowrobotics-rg --query properties.configuration.ingress.fqdn -o tsv
```

Save this domain name (it will look like `sparrowrobotics.lemonriver-f1d6d304.westus.azurecontainerapps.io`).

#### Step 2: Try to add the hostname which will fail but give you the validation information

```bash
az containerapp hostname add --name sparrowrobotics --resource-group sparrowrobotics-rg --hostname www.sparrowrobotics.ca
```

This command will fail with an error message that includes the required validation ID, similar to:
```
(InvalidCustomHostNameValidation) A TXT record pointing from asuid.www.sparrowrobotics.ca to [VALIDATION_ID] was not found.
```

You should extract the validation ID from this error message and use it to create the required DNS records.

#### Step 3: Configure DNS Records in NameCheap

1. Log in to your NameCheap account
2. Go to "Domain List" and select your domain (sparrowrobotics.ca)
3. Click "Manage" and then select the "Advanced DNS" tab
4. Add the following records:

   a. CNAME Record for www:
   ```
   Type: CNAME
   Host: www
   Value: sparrowrobotics.lemonriver-f1d6d304.westus.azurecontainerapps.io
   TTL: Automatic
   ```

   b. TXT Record for domain validation:
   ```
   Type: TXT
   Host: asuid.www
   Value: 90DF5A6B3BE4C0371AC6AD22A95A4041B59FE821794EC23A17E5D829578064DE
   TTL: Automatic
   ```

   c. If you want to use the apex domain (sparrowrobotics.ca without www):
   ```
   Type: A
   Host: @
   Value: [IP address of Azure's load balancer]
   TTL: Automatic
   ```
   
   Note: For the apex domain, you might need to use Azure's DNS service or a service like Cloudflare that supports CNAME flattening, as NameCheap doesn't support ALIAS records.
   
   Wait for DNS propagation (15 minutes to 48 hours)

#### Step 4: Try adding the hostname again:

```bash
az containerapp hostname add --name sparrowrobotics --resource-group sparrowrobotics-rg --hostname www.sparrowrobotics.ca
```

After you add your custom domain with `az containerapp hostname add`, you need to explicitly bind it with a managed certificate using:

```bash
az containerapp hostname bind \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --hostname www.sparrowrobotics.ca \
  --environment sparrowrobotics-env \
```

#### Step 5: Enable HTTPS for Your Custom Domain

Azure Container Apps automatically provisions and manages SSL certificates for custom domains. Once your domain is validated, HTTPS will be automatically enabled.

To verify:
```bash
# Check if HTTPS is enabled
az containerapp hostname list --name sparrowrobotics --resource-group sparrowrobotics-rg --query "[?hostname=='www.sparrowrobotics.ca'].bindingType" -o tsv
```

The output should be `TLS` if HTTPS is enabled.

## Setting Up GitHub Actions for CI/CD

Make sure you have a `.github/workflows/azure-deploy.yml` file

To set up the GitHub secrets:

#### Step 1: Create a service principal:
```bash
az ad sp create-for-rbac --name "sparrowrobotics-github" --role contributor \
  --scopes /subscriptions/5a3935a9-d61b-444f-a13f-194cd9bd49ad/resourceGroups/sparrowrobotics-rg \
  --sdk-auth
```

#### Step 2: Add the result JSON output as a GitHub secret (via GUI) named `AZURE_CREDENTIALS`

#### Step 3: Add ACR credentials as secrets:
```bash
ACR_USERNAME=$(az acr credential show -n sparrowroboticsacr --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show -n sparrowroboticsacr --query "passwords[0].value" -o tsv)
```

#### Step 4: Add these as GitHub secrets `ACR_USERNAME` and `ACR_PASSWORD`



## Future Enhancements

### 1. Multi-Container Setup with Nginx (Optional, as I had troubles with it)

For additional security and performance benefits, you could enhance the deployment with a multi-container setup that includes Nginx as a reverse proxy:

```bash
# Build and push the Nginx image
az acr build --registry sparrowroboticsacr --image sparrowrobotics-nginx:latest --file nginx/azure/Dockerfile nginx/azure

# Add the Nginx container
az containerapp update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --container-name nginx \
  --image sparrowroboticsacr.azurecr.io/sparrowrobotics-nginx:latest \
  --cpu 0.5 \
  --memory 1.0Gi

# Update the ingress to route traffic through Nginx
az containerapp ingress update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --target-port 80
```


## Monitoring and Troubleshooting

After deployment, you can monitor your application and troubleshoot any issues:

```bash
# View Container App logs
az containerapp logs show --name sparrowrobotics --resource-group sparrowrobotics-rg --follow

# Check the status of your containers
az containerapp revision list --name sparrowrobotics --resource-group sparrowrobotics-rg

# Get detailed information about your Container App
az containerapp show --name sparrowrobotics --resource-group sparrowrobotics-rg
```

This approach ensures your credentials are securely stored in Azure Key Vault and injected into your application without being exposed in your code, GitHub repository, or Docker images. The multi-container setup with Nginx is properly deployed to Azure Container Apps, and your custom domain from NameCheap is correctly configured.
