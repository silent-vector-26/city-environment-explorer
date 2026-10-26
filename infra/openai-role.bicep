targetScope = 'resourceGroup'

@description('Name of the existing Azure OpenAI / AI Services account in this resource group.')
param accountName string

@description('Object ID of the principal that receives the role.')
param principalId string

@description('Stable seed for the role assignment name, known at deployment start.')
param assignmentSeed string

var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: accountName
}

resource openAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, assignmentSeed, cognitiveServicesOpenAiUserRoleId)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
