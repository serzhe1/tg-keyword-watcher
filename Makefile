.PHONY: help deploy up down restart logs ps rebuild rebuild-clean prune destroy

PROJECT := tg-keyword-watcher

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  deploy         Build and start services"
	@echo "  up             Start services without rebuild"
	@echo "  down           Stop services"
	@echo "  restart        Restart services"
	@echo "  logs           Tail app logs"
	@echo "  ps             Show running containers"
	@echo "  rebuild        Rebuild app image and restart"
	@echo "  rebuild-clean  Rebuild with prune of unused images"
	@echo "  prune          Remove unused Docker images"
	@echo "  destroy        Stop and remove containers, volumes, images, and local data"

deploy:
	docker compose up -d --build

up:
	docker compose up -d

down:
	docker compose down --remove-orphans

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=200 app

ps:
	docker compose ps

rebuild:
	docker compose down --remove-orphans
	docker compose build --no-cache
	docker compose up -d

rebuild-clean:
	docker compose down --remove-orphans
	docker image prune -a -f
	docker compose build --no-cache
	docker compose up -d

prune:
	docker image prune -a -f

destroy:
	docker compose down -v --rmi all --remove-orphans
	rm -rf data
