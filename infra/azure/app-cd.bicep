targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentName string = 'dev'
@description('GitHub OIDC가 발급하는 저장소의 immutable subject prefix')
param githubSubjectPrefix string = 'repo:dt4-proj3-team3@314105294/watchback@1337157824'

var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id, 'watchback-${environmentName}'), 0, 7)
var registryName = 'acrwatchback${environmentName}${suffix}'
var acrPushRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
var containerAppsContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '358470bc-b998-42bd-ab17-a7e34c199c0f')
var commonTags = {
  project: 'watchback'
  environment: environmentName
  issue: '134'
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource backend 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: 'ca-watchback-api-${environmentName}'
}

resource frontend 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: 'ca-watchback-web-${environmentName}'
}

resource cdIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-watchback-cd-${environmentName}'
  location: location
  tags: commonTags
}

resource githubMainFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: cdIdentity
  name: 'github-main'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:ref:refs/heads/main'
  }
}

resource registryPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, cdIdentity.id, acrPushRoleId)
  scope: registry
  properties: {
    principalId: cdIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRoleId
  }
}

resource backendDeploy 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(backend.id, cdIdentity.id, containerAppsContributorRoleId)
  scope: backend
  properties: {
    principalId: cdIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: containerAppsContributorRoleId
  }
}

resource frontendDeploy 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(frontend.id, cdIdentity.id, containerAppsContributorRoleId)
  scope: frontend
  properties: {
    principalId: cdIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: containerAppsContributorRoleId
  }
}

output cdClientId string = cdIdentity.properties.clientId
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
