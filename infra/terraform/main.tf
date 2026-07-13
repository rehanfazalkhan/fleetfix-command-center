data "aws_caller_identity" "current" {}

resource "aws_dynamodb_table" "cases" {
  name         = "fleetfix-cases-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "case_id"

  attribute {
    name = "case_id"
    type = "S"
  }

  attribute {
    name = "gsi_pk"
    type = "S"
  }

  attribute {
    name = "gsi_sk"
    type = "S"
  }

  global_secondary_index {
    name            = "by_created"
    hash_key        = "gsi_pk"
    range_key       = "gsi_sk"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = var.environment == "production"
  }

  server_side_encryption {
    enabled = true
  }
}

resource "aws_cloudwatch_log_group" "fleetfix" {
  name              = "/fleetfix/${var.environment}/command-center"
  retention_in_days = 30
}

data "aws_iam_policy_document" "runtime_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = "fleetfix-agentcore-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.runtime_trust.json
}

data "aws_iam_policy_document" "runtime" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["arn:aws:bedrock:*::foundation-model/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.cases.arn, "${aws_dynamodb_table.cases.arn}/index/by_created"]
  }

  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.fleetfix.arn}:*"]
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "fleetfix-least-privilege"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime.json
}
