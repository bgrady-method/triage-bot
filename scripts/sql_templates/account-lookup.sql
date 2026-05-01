-- Template: account-lookup
-- Description: Find a Method account by name, subdomain, database name (CompanyAccount), or RecordID.
-- Source: ported from claude-plugin/templates/sql/account-lookup.sql, parameterized.
--
-- Run against AlocetSystem on a cluster that has it (C1, C3-C5).
-- C2 has accounts but NO AlocetSystem; this template will return empty there.
--
-- @param search:str

SELECT TOP 20
  RecordID,
  CompanyAccount        AS DatabaseName,
  AccountCompanyName    AS DisplayName,
  SubdomainList         AS Subdomain,
  CompanyUID            AS AccountGuid,
  IsActive,
  MethodSignUpDate      AS SignupDate,
  MethodCancellationDate AS CancelDate,
  SyncType,
  SubscriptionStatus
FROM dbo.CustomerMethodAccount WITH (NOLOCK)
WHERE CompanyAccount        LIKE '%' + :search + '%'
   OR AccountCompanyName    LIKE '%' + :search + '%'
   OR AccountFriendlyName   LIKE '%' + :search + '%'
   OR SubdomainList         LIKE '%' + :search + '%'
ORDER BY IsActive DESC, CompanyAccount
