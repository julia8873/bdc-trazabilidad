-- Ejecutar conectado como postgres (rol superusuario) en la base de datos mapeo_db
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'metrics_user') THEN
      CREATE ROLE metrics_user WITH LOGIN PASSWORD 'metrics_pass';
   END IF;
END
$do$;

CREATE SCHEMA IF NOT EXISTS metrics AUTHORIZATION metrics_user;
GRANT USAGE ON SCHEMA metrics TO metrics_user;
REVOKE ALL ON SCHEMA public FROM metrics_user;
