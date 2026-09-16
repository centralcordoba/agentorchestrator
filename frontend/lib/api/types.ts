import type { components, paths } from "./schema";

type Schemas = components["schemas"];

export type Requirement = Schemas["RequirementOut"];
export type RequirementSummary = Schemas["RequirementSummaryOut"];
export type RunSummary = Schemas["RunSummaryOut"];
export type Attachment = Schemas["AttachmentOut"];
export type Repo = Schemas["RepoOut"];
export type RepoFile = Schemas["RepoFileOut"];
export type Plan = Schemas["PlanOut"];
export type PlanItem = Schemas["PlanItemOut"];
export type PlanWarning = Schemas["PlanWarningOut"];
export type PlanView = Schemas["PlanViewOut"];
export type Run = Schemas["RunOut"];
export type AgentExecution = Schemas["AgentExecutionOut"];
export type LLMCall = Schemas["LLMCallOut"];
export type TraceEvent = Schemas["TraceEventOut"];
export type RunDetail = Schemas["RunDetailOut"];
export type Deliverables = Schemas["DeliverablesOut"];
export type Finding = Schemas["FindingOut"];
export type Usage = Schemas["UsageOut"];
export type AgentCatalog = Schemas["AgentCatalogOut"];
export type AgentDefinition = Schemas["AgentDefinitionOut"];
export type ModelCatalog = Schemas["ModelCatalogOut"];
export type AgentProfile = Schemas["AgentProfileOut"];
export type AuditEntry = Schemas["AuditEntryOut"];
export type AuditVerification = Schemas["AuditVerificationOut"];
export type Secret = Schemas["SecretOut"];
export type SecretPage = Schemas["SecretPage"];
export type SaveSecretBody = Schemas["SaveSecretIn"];
export type SecretKind = Schemas["SecretKind"];
export type Health = Schemas["HealthOut"];
export type ApiErrorBody = Schemas["ApiError"];

export type CreateRequirementBody = Schemas["CreateRequirementIn"];
export type StartRunBody = Schemas["StartRunIn"];
export type NewAttachment = Schemas["AttachmentIn"];
export type ClassifyPhiBody = Schemas["ClassifyPhiIn"];
export type ConnectRepoBody = Schemas["ConnectRepoIn"];

export type User = Schemas["UserOut"];
export type UserPage = Schemas["UserPage"];
export type SessionInfo = Schemas["SessionOut"];
export type AuthCatalog = Schemas["CatalogOut"];
export type LoginBody = Schemas["LoginIn"];
export type CreateUserBody = Schemas["CreateUserIn"];
export type UpdateUserBody = Schemas["UpdateUserIn"];
export type Role = Schemas["Role"];
export type UpdatePlanBody = Schemas["UpdatePlanIn"];

export type RequirementPage = Schemas["RequirementPage"];
export type RunPage = Schemas["RunPage"];
export type AuditPage = Schemas["AuditPage"];

/** Rutas disponibles, por si hace falta tipar una petición nueva. */
export type ApiPaths = paths;

export type PhiClassification = Schemas["PhiClassification"];
export type AttachmentKind = Schemas["AttachmentKind"];
export type AgentId = Schemas["AgentId"];
