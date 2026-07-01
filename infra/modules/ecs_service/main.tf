locals {
  # Derive cluster name from ARN: arn:aws:ecs:region:account:cluster/<name>
  cluster_name = split("/", var.cluster_id)[1]

  base_container = {
    name        = var.container_name
    image       = var.image_url
    environment = var.environment_vars
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.main.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }

  port_config = var.container_port > 0 ? {
    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]
  } : {}

  command_config = length(var.command) > 0 ? { command = var.command } : {}

  stop_timeout_config = var.stop_timeout > 0 ? { stopTimeout = var.stop_timeout } : {}

  health_check_config = var.health_check_path != "" ? {
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}${var.health_check_path} || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  } : {}

  container_definition = merge(
    local.base_container,
    local.port_config,
    local.command_config,
    local.stop_timeout_config,
    local.health_check_config,
  )
}

resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Name = "${var.name}-logs" })
}

resource "aws_ecs_task_definition" "main" {
  family                   = "${var.name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([local.container_definition])

  tags = merge(var.tags, { Name = "${var.name}-task" })
}

resource "aws_ecs_service" "main" {
  name            = "${var.name}-service"
  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  enable_execute_command = true

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = true
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn != "" ? [1] : []
    content {
      target_group_arn = var.target_group_arn
      container_name   = var.container_name
      container_port   = var.container_port
    }
  }

  tags = merge(var.tags, { Name = "${var.name}-service" })
}

resource "aws_appautoscaling_target" "main" {
  count              = var.autoscaling_enabled ? 1 : 0
  max_capacity       = var.autoscaling_max
  min_capacity       = var.autoscaling_min
  resource_id        = "service/${local.cluster_name}/${aws_ecs_service.main.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  count              = var.autoscaling_enabled ? 1 : 0
  name               = "${var.name}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.main[0].resource_id
  scalable_dimension = aws_appautoscaling_target.main[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.main[0].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = var.autoscaling_cpu_target
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
