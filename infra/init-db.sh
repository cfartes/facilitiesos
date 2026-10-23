#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set app_password="$APP_DB_PASSWORD" --set platform_password="$PLATFORM_DB_PASSWORD" <<'SQL'
CREATE ROLE facilities_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE facilities_platform LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD :'platform_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE facilities TO facilities_app, facilities_platform;
SQL
