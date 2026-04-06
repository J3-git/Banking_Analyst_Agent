# variables
SERVERS=docker compose -f Servers/docker-compose.server.yml \
        --env-file Servers/.env.server

APP=docker compose -f docker-compose.app.yml \
    --env-file src/.env.app

up:
	$(SERVERS) up -d
	$(APP) run --rm -it app
# 	$(APP) up --build

down:
	$(APP) down
	$(SERVERS) down

logs-app:
	$(APP) logs -f

logs-servers:
	$(SERVERS) logs -f

clean:
	$(APP) down -v --remove-orphans
	$(SERVERS) down -v --remove-orphans