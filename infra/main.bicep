targetScope = 'resourceGroup'

@description('Azure region for the Container Apps environment and related resources.')
param location string = resourceGroup().location

@description('Name of the Azure Container Registry. Must be globally unique and contain only lowercase letters and numbers.')
@minLength(5)
@maxLength(50)
param acrName string = 'cee${uniqueString(subscription().id, resourceGroup().id)}'

@description('Name of the Container App.')
param containerAppName string = 'cee-${uniqueString(resourceGroup().id)}'

@description('Name of the Container Apps managed environment.')
param containerAppsEnvironmentName string = 'cee-env-${uniqueString(resourceGroup().id)}'

@description('Container image. Used when deployApp is true; provide an image already pushed to the provisioned registry.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Create the public Container App after the registry and environment exist. Set false for the first deployment before building the app image.')
param deployApp bool = true

@description('Minimum active replicas. One keeps the AirNow data cache warm; zero allows scale-to-zero but loses the cache and causes cold starts.')
@minValue(0)
@maxValue(10)
param minReplicas int = 1

@description('Maximum active replicas for the portfolio demo.')
@minValue(1)
@maxValue(10)
param maxReplicas int = 2

@description('Optional Azure OpenAI resource endpoint. When empty, model summaries remain unconfigured.')
param azureOpenAiEndpoint string = ''

@description('Optional Azure OpenAI deployment name. The app uses its managed identity when configured.')
param azureOpenAiDeployment string = ''

@description('Optional name of the existing Azure OpenAI account. With azureOpenAiResourceGroup, grants the app identity the Cognitive Services OpenAI User role.')
param azureOpenAiAccountName string = ''

@description('Resource group of the existing Azure OpenAI account, in the same subscription.')
param azureOpenAiResourceGroup string = ''

@description('Optional EPA AirNow API key. When empty, the app shows labeled sample data.')
@secure()
param airNowApiKey string = ''

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var hasAirNowKey = !empty(airNowApiKey)
var grantOpenAiAccess = deployApp && !empty(azureOpenAiAccountName) && !empty(azureOpenAiResourceGroup)

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'cee-logs-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource registryPullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'cee-acr-pull-${uniqueString(resourceGroup().id)}'
  location: location
}

// Grant pull access before creating the app revision so the registry image can be fetched without admin credentials.
resource registryPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, registryPullIdentity.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: registryPullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// The first workflow deployment creates the shared foundation; the second adds the app after its image is pushed.
resource containerApp 'Microsoft.App/containerApps@2025-01-01' = if (deployApp) {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${registryPullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8501
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: registryPullIdentity.id
        }
      ]
      secrets: hasAirNowKey
        ? [
            {
              name: 'airnow-api-key'
              value: airNowApiKey
            }
          ]
        : []
    }
    template: {
      containers: [
        {
          name: 'city-environment-explorer'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(
            [
              {
                name: 'APP_ENV'
                value: 'production'
              }
            ],
            !empty(azureOpenAiEndpoint) && !empty(azureOpenAiDeployment)
              ? [
                  {
                    name: 'AZURE_OPENAI_ENDPOINT'
                    value: azureOpenAiEndpoint
                  }
                  {
                    name: 'AZURE_OPENAI_DEPLOYMENT'
                    value: azureOpenAiDeployment
                  }
                ]
              : [],
            hasAirNowKey
              ? [
                  {
                    name: 'AIRNOW_API_KEY'
                    secretRef: 'airnow-api-key'
                  }
                ]
              : []
          )
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/_stcore/health'
                port: 8501
                scheme: 'HTTP'
              }
              periodSeconds: 5
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/_stcore/health'
                port: 8501
                scheme: 'HTTP'
              }
              periodSeconds: 30
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    registryPullRoleAssignment
  ]
}

module openAiAccess 'openai-role.bicep' = if (grantOpenAiAccess) {
  name: 'cee-openai-access'
  scope: resourceGroup(azureOpenAiResourceGroup)
  params: {
    accountName: azureOpenAiAccountName
    principalId: containerApp!.identity.principalId
    assignmentSeed: containerAppName
  }
}

output acrName string = registry.name
output acrLoginServer string = registry.properties.loginServer
output containerAppName string = containerAppName
output containerAppsEnvironmentName string = containerAppsEnvironment.name
