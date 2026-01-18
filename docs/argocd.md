# ArgoCD Integration

This document explains how to use `make-argocd-fly` to implement the ArgoCD app-of-apps pattern, which allows you to manage multiple applications in a Kubernetes cluster using ArgoCD.

The app-of-apps pattern is a powerful way to structure your applications in a hierarchical manner, where one top-level application (the "bootstrap" application) manages the deployment of other applications. This approach simplifies the management of complex deployments and allows for better organization of resources.

## 🎯 What is the App-of-Apps Pattern?

The [app-of-apps pattern](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/) is a design pattern in ArgoCD where a single ArgoCD `Application` resource is used to manage multiple other `Application` resources. This top-level application (often called the "bootstrap" application) serves as a parent that deploys and manages child applications. Each child application can have its own configuration and can be deployed independently, but they are all managed under the umbrella of the parent application.

This pattern is particularly useful for large projects with multiple microservices or components, as it allows you to group related applications together and manage them as a single unit.

## 🚀 Using `make-argocd-fly` for App-of-Apps

`make-argocd-fly` simplifies the implementation of the app-of-apps pattern by automatically generating the necessary ArgoCD `Application` resources based on your configuration. You can define your applications and their relationships in a structured way, and `make-argocd-fly` will handle the generation of the appropriate YAML files for you.

## 🛠️ Configuration Example

To set up the app-of-apps pattern using `make-argocd-fly`, you need to define your applications and their relationships in the configuration file. Here’s an example of how to do this:

```yaml
envs:
  <environment_name>:
    apps:
      <bootstrap_application>: {}  ## application that will deploy other applications
      <application_name>:
        params:
          parent_app: <bootstrap_application>  ## application name that will deploy this application
          parent_app_env: <environment_name>  ## environment name for the parent application, default: current environment
vars:
  argocd:
    namespace: <argocd_namespace>  ## (OPTIONAL) namespace for ArgoCD `Application` resource, default: argocd
    sync_wave: <application_sync_wave>  ## (OPTIONAL) `sync_wave` annotation for ArgoCD `Application` resource
    finalizers: <argocd_finalizers>  ## (OPTIONAL) default: []
    project: <project_name>  ## (OPTIONAL) ArgoCD project name, default: default
    source:
      repo_url: <argocd_repo_url>  ## URL of the Git repository
      target_revision: <argocd_target_revision>  ## target revision for the Git repository, default: HEAD
      directory:
        recurse: <true|false>  ## (OPTIONAL) not set by default
    destination:
      server: <kube_apiserver>  ## kube-apiserver address, default: https://kubernetes.default.svc
      namespace: <namespace>  ## (OPTIONAL) default namespace where the application resources will be deployed, default: argocd
    sync_policy: <argocd_sync_policy>  ## (OPTIONAL) default: {}
    ignoreDifferences: <argocd_ignoreDifferences>  ## (OPTIONAL) default: []
```

Parameters `parent_app` and `parent_app_env` are used to define the parent application and its environment for each child application. This allows you to create a hierarchy where the bootstrap application manages the deployment of other applications.

## Local vs ArgoCD

| Capability | Local (kubectl) | ArgoCD |
|-----------|------------------|--------|
| Render manifests | ✅ | ✅ |
| Auto-sync/reconcile | ❌ | ✅ |
| App-of-Apps hierarchy | ❌ | ✅ |
| Works offline | ✅ | ❌ |
| Best for | quick local testing | managed GitOps in clusters |

For real environments (`dev`, `staging`, `prod`), define separate environments and (optionally) `parent_app` relations to generate ArgoCD `Application` CRs. For `local`, deploy the rendered YAML files via `kubectl`.
