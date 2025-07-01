# Updated Deployment Steps for Azure with Multi-Container Setup and Custom Domain

I've reviewed your deployment_steps.md file and will add the necessary steps for implementing a multi-container setup with Nginx and configuring your NameCheap custom domain. Here's the updated guide:

## Multi-Container Setup for Azure Container Apps

Your current setup uses two containers (web application and Nginx) as defined in your `docker-compose.prod.yaml`. To properly deploy this architecture to Azure Container Apps, we need to add specific steps after Step 6 in your current guide:

### Step 6a: Create a Docker Compose File for Azure Container Apps

Create a new file called `azure-compose.yaml` in your project root:

```yaml
version: '2.0'
services:
  web:
    image: ${REGISTRY_URL}/sparrowrobotics-web:latest
    environment:
      - MAIL_USERNAME=${MAIL_USERNAME}
      - MAIL_PASSWORD=${MAIL_PASSWORD}
      - MAIL_TO=${MAIL_TO}
      - MAIL_FROM=${MAIL_FROM}
    expose:
      - "8000"

  nginx:
    image: ${REGISTRY_URL}/sparrowrobotics-nginx:latest
    depends_on:
      - web
    ports:
      - "80:80"
```

### Step 6b: Create a Custom Nginx Image for Azure

1. Create a new Dockerfile for Nginx:

```bash
# Create a directory for the Nginx Dockerfile
mkdir -p nginx/azure

# Create a Dockerfile for Nginx
cat > nginx/azure/Dockerfile << 'EOF'
FROM nginx:latest
COPY default.conf /etc/nginx/conf.d/default.conf
EOF

# Copy your existing Nginx config
cp nginx/default.conf nginx/azure/
```

2. Update the Nginx configuration for Azure:

```bash
# Update the Nginx configuration to use the internal service name
cat > nginx/azure/default.conf << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

### Step 6c: Build and Push Both Images to ACR

```bash
# Build and push the web application image
az acr build --registry sparrowroboticsacr --image sparrowrobotics-web:latest --file Dockerfile.prod .

# Build and push the Nginx image
az acr build --registry sparrowroboticsacr --image sparrowrobotics-nginx:latest --file nginx/azure/Dockerfile nginx/azure
```

## Step 6d: Deploy the Multi-Container Application

Instead of using a YAML file directly (which was causing the error), use the following Azure CLI commands to create and configure your multi-container application:

```bash
# Create the Container App with managed identity
az containerapp create \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --environment sparrowrobotics-env \
  --registry-server sparrowroboticsacr.azurecr.io \
  --registry-username sparrowroboticsacr \
  --registry-password $(az acr credential show -n sparrowroboticsacr --query "passwords[0].value" -o tsv) \
  --ingress external \
  --target-port 80 \
  --system-assigned

# Get the principal ID of the Container App
principalId=$(az containerapp identity show --name sparrowrobotics --resource-group sparrowrobotics-rg --query principalId -o tsv)

# Grant the Container App access to Key Vault secrets
az role assignment create \
  --assignee $principalId \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show --name sparrowrobotics-kv --query id -o tsv)

# Update the Container App to use multiple containers
az containerapp update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --container-name web \
  --image sparrowroboticsacr.azurecr.io/sparrowrobotics-web:latest

# Add the Nginx container
az containerapp update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --container-name nginx \
  --image sparrowroboticsacr.azurecr.io/sparrowrobotics-nginx:latest \
  --container-command "" \
  --container-args "" \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 3

# Configure the secrets for the web container
az containerapp secret set \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --secrets \
    mail-username=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-USERNAME,identityref:system \
    mail-password=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-PASSWORD,identityref:system \
    mail-to=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-TO,identityref:system \
    mail-from=keyvaultref:https://sparrowrobotics-kv.vault.azure.net/secrets/MAIL-FROM,identityref:system

# Set environment variables for the web container
az containerapp update \
  --name sparrowrobotics \
  --resource-group sparrowrobotics-rg \
  --container-name web \
  --set-env-vars \
    MAIL_USERNAME=secretref:mail-username \
    MAIL_PASSWORD=secretref:mail-password \
    MAIL_TO=secretref:mail-to \
    MAIL_FROM=secretref:mail-from
```

## Custom Domain Configuration with NameCheap

After deploying your application, you'll need to configure your custom domain from NameCheap. Here are the detailed steps:

### Step 1: Get Your Azure Container App's Default Domain

```bash
# Get the default domain of your Container App
az containerapp show --name sparrowrobotics --resource-group sparrowrobotics-rg --query properties.configuration.ingress.fqdn -o tsv
```

Save this domain name (it will look like `sparrowrobotics.randomstring.westus.azurecontainerapps.io`).

### Step 2: Add Your Custom Domain to Azure Container Apps

```bash
# Add your custom domain to the Container App
az containerapp hostname add --name sparrowrobotics --resource-group sparrowrobotics-rg --hostname www.sparrowrobotics.ca
```

### Step 3: Get the Validation Records

```bash
# Get the validation records for your custom domain
az containerapp hostname list --name sparrowrobotics --resource-group sparrowrobotics-rg
```

This will return a JSON object containing the validation records you need to add to your DNS configuration.

### Step 4: Configure DNS Records in NameCheap

1. Log in to your NameCheap account
2. Go to "Domain List" and select your domain (sparrowrobotics.ca)
3. Click "Manage" and then select the "Advanced DNS" tab
4. Add the following records:

   a. CNAME Record for www:
   ```
   Type: CNAME
   Host: www
   Value: [your-container-app-default-domain] (from Step 1)
   TTL: Automatic
   ```

   b. TXT Record for domain validation:
   ```
   Type: TXT
   Host: asuid.www
   Value: [validation-id] (from Step 3)
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

### Step 5: Verify Domain Ownership

```bash
# Check the validation status of your custom domain
az containerapp hostname show --name sparrowrobotics --resource-group sparrowrobotics-rg --hostname www.sparrowrobotics.ca
```

It may take some time for DNS changes to propagate (typically 15 minutes to 48 hours).

### Step 6: Enable HTTPS for Your Custom Domain

Azure Container Apps automatically provisions and manages SSL certificates for custom domains. Once your domain is validated, HTTPS will be automatically enabled.

To verify:
```bash
# Check if HTTPS is enabled
az containerapp hostname show --name sparrowrobotics --resource-group sparrowrobotics-rg --hostname www.sparrowrobotics.ca --query properties.bindingType
```

## Update GitHub Actions for Multi-Container Deployment

Update your `.github/workflows/azure-deploy.yml` file to support the multi-container setup:

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
    
    - name: Build and push images to ACR
      uses: azure/docker-login@v1
      with:
        login-server: sparrowroboticsacr.azurecr.io
        username: ${{ secrets.ACR_USERNAME }}
        password: ${{ secrets.ACR_PASSWORD }}
    
    - run: |
        # Build and push web app image
        docker build -f Dockerfile.prod -t sparrowroboticsacr.azurecr.io/sparrowrobotics-web:${{ github.sha }} .
        docker push sparrowroboticsacr.azurecr.io/sparrowrobotics-web:${{ github.sha }}
        
        # Build and push Nginx image
        docker build -f nginx/azure/Dockerfile -t sparrowroboticsacr.azurecr.io/sparrowrobotics-nginx:${{ github.sha }} nginx/azure
        docker push sparrowroboticsacr.azurecr.io/sparrowrobotics-nginx:${{ github.sha }}
    
    - name: Update Container App YAML
      run: |
        cat > container-app-update.yaml << EOF
        properties:
          template:
            containers:
              - name: web
                image: sparrowroboticsacr.azurecr.io/sparrowrobotics-web:${{ github.sha }}
              - name: nginx
                image: sparrowroboticsacr.azurecr.io/sparrowrobotics-nginx:${{ github.sha }}
        EOF
    
    - name: Deploy to Azure Container Apps
      run: |
        az containerapp update --resource-group sparrowrobotics-rg --name sparrowrobotics --yaml container-app-update.yaml
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

These additions to your deployment steps will ensure that your multi-container setup with Nginx is properly deployed to Azure Container Apps and that your custom domain from NameCheap is correctly configured.