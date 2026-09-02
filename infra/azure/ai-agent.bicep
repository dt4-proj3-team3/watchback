targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentName string = 'dev'
@description('기존 Watchback Backend가 사용하는 사용자 할당 Managed Identity 이름')
param runtimeIdentityName string = 'id-watchback-${environmentName}'
@description('Azure OpenAI에 배포할 모델 이름')
param modelName string = 'gpt-5.6-luna'
@description('검증된 Azure OpenAI 모델 버전')
param modelVersion string = '2026-07-09'
@description('Azure OpenAI deployment 이름')
param deploymentName string = modelName
@minValue(1)
@description('GlobalStandard 처리량 단위. GPT-5.6은 1 단위가 1K TPM이다.')
param deploymentCapacity int = 10

var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id, 'watchback-${environmentName}'), 0, 7)
var accountName = 'oai-watchback-${environmentName}-${suffix}'
var openAIUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var commonTags = {
  project: 'watchback'
  environment: environmentName
  capability: 'ai-agent'
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: runtimeIdentityName
  location: location
  tags: commonTags
}

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
  tags: commonTags
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource runtimeOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, runtimeIdentity.id, openAIUserRoleId)
  scope: account
  properties: {
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: openAIUserRoleId
  }
}

output accountName string = account.name
output endpoint string = account.properties.endpoint
output deploymentName string = deployment.name
output model string = '${modelName}:${modelVersion}'
