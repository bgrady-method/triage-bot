-- Template: cluster-resolve
-- Description: Verify a database exists on the connected cluster. Returns name, state, server.
-- Source: ported from claude-plugin/templates/sql/cluster-resolve.sql, parameterized.
--
-- @param database:str

SELECT
  @@SERVERNAME    AS ServerName,
  name            AS DatabaseName,
  state_desc      AS State
FROM sys.databases
WHERE name = :database
