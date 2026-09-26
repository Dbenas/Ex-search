terraform {
  required_version = ">= 1.8"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Remote state in a versioned bucket; create it once before `terraform init`.
  backend "gcs" {
    prefix = "curator"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
