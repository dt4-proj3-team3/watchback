targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentName string = 'dev'
@description('비밀을 주입하는 현재 Azure 사용자 또는 서비스 주체의 Object ID')
param deployerObjectId string

var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id, 'watchback-${environmentName}'), 0, 7)
var registryName = 'acrwatchback${environmentName}${suffix}'
var keyVaultName = 'kv-watchback-${environmentName}-${suffix}'
var keyVaultSecretsOfficerRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var commonTags = {
  project: 'watchback'
  environment: environmentName
  issue: '120'
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
  tags: commonTags
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: tenant().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
  }
  tags: commonTags
}

resource deployerSecretAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, deployerObjectId, keyVaultSecretsOfficerRoleId)
  scope: keyVault
  properties: {
    principalId: deployerObjectId
    principalType: 'User'
    roleDefinitionId: keyVaultSecretsOfficerRoleId
  }
}

output registryName string = registry.name
output registryServer string = registry.properties.loginServer
output keyVaultName string = keyVault.name
