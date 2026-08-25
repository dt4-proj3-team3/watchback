targetScope = 'resourceGroup'

@description('ACR에 게시한 세 이미지에 공통으로 적용한 태그')
param imageTag string

@secure()
@description('PostgreSQL 관리자 비밀번호. 배포 기록에는 표시되지 않는다.')
param postgresAdminPassword string

@description('배포를 실행하는 개발자의 공인 IPv4 주소')
param developerIp string

@description('Key Vault에 github-token을 주입한 경우 Dependabot Job을 배포한다.')
param deployDependabotJob bool = false

param location string = resourceGroup().location
param environmentName string = 'dev'
param postgresAdminUser string = 'watchbackadmin'
param databaseName string = 'watchback'

var suffix = substring(uniqueString(subscription().subscriptionId, resourceGroup().id, 'watchback-${environmentName}'), 0, 7)
var registryName = 'acrwatchback${environmentName}${suffix}'
var keyVaultName = 'kv-watchback-${environmentName}-${suffix}'
var postgresName = 'pg-watchback-${environmentName}-${suffix}'
var commonTags = {
  project: 'watchback'
  environment: environmentName
  issue: '120'
}
var databaseUrl = 'postgresql+psycopg://${postgresAdminUser}:${uriComponent(postgresAdminPassword)}@${postgres.properties.fullyQualifiedDomainName}:5432/${databaseName}?sslmode=require'
var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var keyVaultSecretsUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-watchback-${environmentName}'
  location: location
  tags: commonTags
}

resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, acrPullRoleId)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleId
  }
}

resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-watchback-${environmentName}'
  location: location
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
  tags: commonTags
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-watchback-${environmentName}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
  }
  tags: commonTags
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource keyVaultRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleId
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    availabilityZone: '1'
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    storage: {
      autoGrow: 'Enabled'
      storageSizeGB: 32
    }
  }
  tags: commonTags
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource developerFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'watchback-developer'
  properties: {
    startIpAddress: developerIp
    endIpAddress: developerIp
  }
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: databaseUrl
  }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-watchback-${environmentName}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logWorkspace.properties.customerId
        sharedKey: logWorkspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
  tags: commonTags
}

resource backend 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-watchback-api-${environmentName}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: databaseUrlSecret.properties.secretUri
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: '${registry.properties.loginServer}/watchback-backend:${imageTag}'
          env: [
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/openapi.json'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  tags: commonTags
  dependsOn: [
    registryPull
    keyVaultRead
  ]
}

resource frontend 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-watchback-web-${environmentName}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerEnvironment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 3000
        transport: 'auto'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${registry.properties.loginServer}/watchback-frontend:${imageTag}'
          env: [
            {
              name: 'WATCHBACK_API_BASE_URL'
              value: 'https://${backend.properties.configuration.ingress.fqdn}'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/dashboard'
                port: 3000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 20
              periodSeconds: 30
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  tags: commonTags
  dependsOn: [
    registryPull
  ]
}

module databaseInitJob 'modules/container-app-job.bicep' = {
  name: 'database-init-job'
  params: {
    name: 'caj-watchback-db-init-${environmentName}'
    location: location
    environmentId: containerEnvironment.id
    image: '${registry.properties.loginServer}/watchback-backend:${imageTag}'
    registryServer: registry.properties.loginServer
    identityId: identity.id
    command: [
      '/bin/sh'
      '-c'
    ]
    args: [
      'python -m alembic upgrade head && python -m watchback_backend.db.demo_seed'
    ]
    environmentVariables: [
      {
        name: 'DATABASE_URL'
        secretRef: 'database-url'
      }
    ]
    secrets: [
      {
        name: 'database-url'
        keyVaultUrl: databaseUrlSecret.properties.secretUri
        identity: identity.id
      }
    ]
    tags: commonTags
  }
  dependsOn: [
    registryPull
    keyVaultRead
    database
  ]
}

module dependabotJob 'modules/container-app-job.bicep' = if (deployDependabotJob) {
  name: 'dependabot-sync-job'
  params: {
    name: 'caj-watchback-dependabot-${environmentName}'
    location: location
    environmentId: containerEnvironment.id
    image: '${registry.properties.loginServer}/watchback-dependabot-sync:${imageTag}'
    registryServer: registry.properties.loginServer
    identityId: identity.id
    environmentVariables: [
      {
        name: 'DATABASE_URL'
        secretRef: 'database-url'
      }
      {
        name: 'GITHUB_TOKEN'
        secretRef: 'github-token'
      }
    ]
    secrets: [
      {
        name: 'database-url'
        keyVaultUrl: databaseUrlSecret.properties.secretUri
        identity: identity.id
      }
      {
        name: 'github-token'
        keyVaultUrl: '${keyVault.properties.vaultUri}secrets/github-token'
        identity: identity.id
      }
    ]
    tags: commonTags
  }
  dependsOn: [
    registryPull
    keyVaultRead
    database
  ]
}

output registryName string = registry.name
output keyVaultName string = keyVault.name
output postgresName string = postgres.name
output databaseName string = database.name
output backendUrl string = 'https://${backend.properties.configuration.ingress.fqdn}'
output frontendUrl string = 'https://${frontend.properties.configuration.ingress.fqdn}'
output databaseInitJobName string = databaseInitJob.outputs.name
output dependabotJobName string = deployDependabotJob ? dependabotJob!.outputs.name : ''
