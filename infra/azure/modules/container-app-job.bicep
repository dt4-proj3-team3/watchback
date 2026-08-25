param name string
param location string
param environmentId string
param image string
param registryServer string
param identityId string
param command array = []
param args array = []
param environmentVariables array = []
param secrets array = []
param cpu string = '0.5'
param memory string = '1Gi'
param replicaTimeout int = 1800
param replicaRetryLimit int = 1
param tags object = {}

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: replicaTimeout
      replicaRetryLimit: replicaRetryLimit
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: registryServer
          identity: identityId
        }
      ]
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: name
          image: image
          command: command
          args: args
          env: environmentVariables
          resources: {
            cpu: json(cpu)
            memory: memory
          }
        }
      ]
    }
  }
  tags: tags
}

output id string = job.id
output name string = job.name
