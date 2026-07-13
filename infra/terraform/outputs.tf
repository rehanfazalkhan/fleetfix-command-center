output "case_table_name" { value = aws_dynamodb_table.cases.name }
output "runtime_execution_role_arn" { value = aws_iam_role.runtime.arn }
