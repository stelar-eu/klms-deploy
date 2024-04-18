#!/bin/sh
set -eu
echo "Upgrading DB schema..."
superset db upgrade
echo "Initializing roles..."
superset init

echo "Creating admin user..."
superset fab create-admin \
                --username admin \
                --firstname Superset \
                --lastname Admin \
                --email admin@superset.com \
                --password stelar1234 \
                || true

if [ -f "/app/configs/import_datasources.yaml" ]; then
    echo "Importing database connections.... "
    superset import_datasources -p /app/configs/import_datasources.yaml
fi
