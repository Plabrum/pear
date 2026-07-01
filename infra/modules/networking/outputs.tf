output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "private_route_table_id" {
  value = aws_route_table.private.id
}

output "alb_sg_id" {
  value = aws_security_group.alb.id
}

output "ecs_tasks_sg_id" {
  value = aws_security_group.ecs_tasks.id
}

output "database_sg_id" {
  value = aws_security_group.database.id
}

output "redis_sg_id" {
  value = aws_security_group.redis.id
}

output "vpc_endpoints_sg_id" {
  value = aws_security_group.vpc_endpoints.id
}
