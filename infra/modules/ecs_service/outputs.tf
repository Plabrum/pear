output "service_name" {
  value = aws_ecs_service.main.name
}

output "service_id" {
  value = aws_ecs_service.main.id
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.main.arn
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.main.name
}
