-- Template: account-active-users
-- Description: Count active users per TenantId inside a single tenant DB.
-- Source: derived from user-lookup.sql (same spiderSecurity table).
--
-- Must run against the account DB (CompanyAccount), NOT AlocetSystem.
-- Caller is responsible for switching DBs via sql_query.py --database <name>
-- before invoking this template.
--
-- @param: (none)

SELECT
  TenantId,
  COUNT(*)                                                                       AS total_users,
  SUM(CASE WHEN spdSecurityActive = 1 THEN 1 ELSE 0 END)                         AS active_users,
  SUM(CASE WHEN spdSecurityActive = 1 AND UserLicenseType IS NOT NULL THEN 1 ELSE 0 END) AS licensed_active_users
FROM spiderSecurity WITH (NOLOCK)
GROUP BY TenantId
ORDER BY active_users DESC
