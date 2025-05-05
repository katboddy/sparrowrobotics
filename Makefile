# Compose files
COMPOSE_DEV=docker-compose.yml
COMPOSE_PROD=docker-compose.prod.yml

# Default target
.PHONY: help
help:
	@echo "Usage:"
	@echo "  make dev         - Run development server with live reload"
	@echo "  make dev-down    - Stop dev containers"
	@echo "  make prod        - Build and run production with nginx"
	@echo "  make prod-down   - Stop production containers"
	@echo "  make clean       - Remove all Docker resources (CAREFUL)"
	@echo "  make rebuild     - Rebuild dev environment"

# Development
.PHONY: dev
dev:
	docker compose -f $(COMPOSE_DEV) up --build

.PHONY: dev-down
dev-down:
	docker compose -f $(COMPOSE_DEV) down -v

# Production
.PHONY: prod
prod:
	docker compose -f $(COMPOSE_PROD) --env-file $(ENV_FILE) up --build -d

.PHONY: prod-down
prod-down:
	docker compose -f $(COMPOSE_PROD) down -v

# Clean all Docker resources
.PHONY: clean
clean:
	docker system prune -a --volumes -f

# Rebuild dev
.PHONY: rebuild
rebuild: dev-down
	docker compose -f $(COMPOSE_DEV) up --build
