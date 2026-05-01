-- Template: user-lookup
-- Description: Find a user inside an account database by email or username.
-- Source: ported from claude-plugin/templates/sql/user-lookup.sql, parameterized.
--
-- Must run against the account DB (CompanyAccount), NOT AlocetSystem.
--
-- @param search:str

SELECT
  spdSecurityId,
  spdSecurityUsername,
  spdSecurityEmail,
  spdSecurityActive,
  TenantId,
  PermittedTenantList,
  IsMasterAdmin,
  IsSuperAdmin,
  UserLicenseType,
  MethodIdentityId
FROM spiderSecurity WITH (NOLOCK)
WHERE spdSecurityEmail    LIKE '%' + :search + '%'
   OR spdSecurityUsername LIKE '%' + :search + '%'
ORDER BY spdSecurityUsername
