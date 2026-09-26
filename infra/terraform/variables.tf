variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "southamerica-east1"
}

variable "github_repository" {
  description = "owner/name of the GitHub repository allowed to deploy."
  type        = string
}

variable "frontend_origin" {
  description = "Vercel URL allowed by CORS."
  type        = string
}

variable "image_tag" {
  description = "Initial image tag; later rollouts come from the deploy workflow."
  type        = string
  default     = "latest"
}
