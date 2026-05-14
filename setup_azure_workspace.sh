#!/bin/bash

# Azure Hochwasser-Scoring MVP Setup Script
set -e

echo "🔧 Starting Azure Workspace Setup..."

# Configuration
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
LOCATION="westeurope"
RESOURCE_GROUP="rg-flood-insurance-mvp"
WORKSPACE_NAME="flood-insurance-workspace"
STORAGE_ACCOUNT="floodinsurancedata"
COMPUTE_NAME="flood-compute"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

echo "✅ Azure CLI found"

# Login to Azure
echo "🔐 Logging in to Azure..."
az login

# Set subscription
if [ -z "$SUBSCRIPTION_ID" ]; then
    echo "Using default subscription"
else
    az account set --subscription "$SUBSCRIPTION_ID"
    echo "✅ Subscription set to: $SUBSCRIPTION_ID"
fi

# Create Resource Group
echo "📦 Creating Resource Group: $RESOURCE_GROUP..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION"
echo "✅ Resource Group created"

# Create Storage Account
echo "💾 Creating Storage Account: $STORAGE_ACCOUNT..."
az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS
echo "✅ Storage Account created"

# Create Blob Container
echo "📁 Creating Blob Container for datasets..."
az storage container create \
    --name datasets \
    --account-name "$STORAGE_ACCOUNT"
echo "✅ Blob Container created"

# Create Azure ML Workspace
echo "🤖 Creating Azure ML Workspace: $WORKSPACE_NAME..."
az ml workspace create \
    --name "$WORKSPACE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --display-name "Hochwasser-Scoring MVP" \
    --description "KI-gestütztes Hochwasserrisiko-Scoring System für Versicherungen"
echo "✅ Azure ML Workspace created"

# Create Compute Cluster
echo "⚙️ Creating Compute Cluster: $COMPUTE_NAME..."
az ml compute create \
    --name "$COMPUTE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$WORKSPACE_NAME" \
    --type amlcompute \
    --min-instances 0 \
    --max-instances 4 \
    --size Standard_D2s_v3
echo "✅ Compute Cluster created"

echo ""
echo "🎉 Azure Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Go to Azure ML Studio: https://ml.azure.com"
echo "2. Select workspace: $WORKSPACE_NAME"
echo "3. Create a new Jupyter Notebook"
echo "4. Run the notebook code from hochwasser-scoring-mvp.ipynb"
echo ""
echo "Configuration Summary:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Workspace: $WORKSPACE_NAME"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  Compute Cluster: $COMPUTE_NAME"
echo "  Location: $LOCATION"
