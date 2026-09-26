output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "github_wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  value = google_service_account.deployer.email
}
