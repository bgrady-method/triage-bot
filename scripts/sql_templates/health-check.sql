-- Template: health-check
-- Description: Connectivity test. Returns server, db, version, time.
-- Source: ported from claude-plugin/templates/sql/health-check.sql

SELECT
  @@SERVERNAME              AS ServerName,
  DB_NAME()                 AS CurrentDB,
  GETDATE()                 AS ServerTime,
  SERVERPROPERTY('ProductVersion') AS SqlVersion,
  SERVERPROPERTY('Edition') AS Edition
