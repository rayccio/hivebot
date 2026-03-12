export enum AgentStatus {
  IDLE = 'IDLE',
  RUNNING = 'RUNNING',
  ERROR = 'ERROR',
  OFFLINE = 'OFFLINE'
}

export enum ReportingTarget {
  PARENT = 'PARENT_AGENT',
  OWNER_DIRECT = 'OWNER_DIRECT',
  BOTH = 'HYBRID'
}

export enum HiveMindAccessLevel {
  ISOLATED = 'ISOLATED',
  SHARED = 'SHARED',
  GLOBAL = 'GLOBAL'
}

export enum UserRole {
  GLOBAL_ADMIN = 'GLOBAL_ADMIN',
  HIVE_ADMIN = 'HIVE_ADMIN',
  HIVE_USER = 'HIVE_USER'
}

export enum SkillType {
  TOOL = 'tool',
  PROMPT = 'prompt',
  WORKFLOW = 'workflow'
}

export enum SkillVisibility {
  PUBLIC = 'public',
  PRIVATE = 'private',
  ORGANIZATION = 'organization'
}

export interface ReasoningConfig {
  model: string;
  temperature: number;
  topP: number;
  maxTokens: number;
  apiKey?: string;
  organizationId?: string;
  cheap_model?: string;
  use_global_default?: boolean;
  use_custom_max_tokens?: boolean;
}

export interface ChannelCredentials {
  webhookUrl?: string;
  botToken?: string;
  chatId?: string;
  apiKey?: string;
  apiSecret?: string;
  clientId?: string;
  mode?: string;
}

export interface ChannelConfig {
  id: string;
  type: 'telegram' | 'discord' | 'whatsapp' | 'slack' | 'custom';
  enabled: boolean;
  credentials: ChannelCredentials;
  status: 'connected' | 'error' | 'disconnected';
  lastPing?: string;
}

export interface FileEntry {
  id: string;
  name: string;
  type: string;
  content: string;
  size: number;
  uploadedAt: string;
}

export interface AgentMemory {
  shortTerm: string[];
  summary: string;
  tokenCount: number;
}

export interface AgentSkill {
  agentId: string;
  skillId: string;
  skillVersionId: string;
  installedAt: string;
  config: Record<string, any>;
  enabled: boolean;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  soulMd: string;
  identityMd: string;
  toolsMd: string;
  status: AgentStatus;
  reasoning: ReasoningConfig;
  reportingTarget: ReportingTarget;
  parentId?: string;
  subAgentIds: string[];
  channels: ChannelConfig[];
  memory: AgentMemory;
  lastActive: string;
  containerId: string;
  userUid?: string;
  localFiles: FileEntry[];
  skills: AgentSkill[];
}

export interface Message {
  id: string;
  from?: string;
  to?: string;
  content: string;
  timestamp: string;
  type?: 'log' | 'chat' | 'internal' | 'error' | 'outbound';
  role?: 'user' | 'model' | 'system';
}

export interface AgentCreate {
  name: string;
  role?: string;
  soulMd: string;
  identityMd: string;
  toolsMd: string;
  reasoning: ReasoningConfig;
  reportingTarget: ReportingTarget;
  parentId?: string;
  userUid?: string;
  channels?: ChannelConfig[];
}

export interface AgentUpdate {
  name?: string;
  role?: string;
  soulMd?: string;
  identityMd?: string;
  toolsMd?: string;
  status?: AgentStatus;
  reasoning?: ReasoningConfig;
  reportingTarget?: ReportingTarget;
  parentId?: string;
  memory?: AgentMemory;
  localFiles?: FileEntry[];
}

export interface HiveMindConfig {
  accessLevel: HiveMindAccessLevel;
  sharedHiveIds: string[];
}

export interface UserAccount {
  id: string;
  username: string;
  password?: string;
  role: UserRole;
  assignedHiveIds: string[];
  lastLogin?: string;
  createdAt: string;
  updatedAt?: string;
  password_changed?: boolean;
}

export interface GlobalSettings {
  loginEnabled: boolean;
  sessionTimeout: number;
  systemName: string;
  maintenanceMode: boolean;
  defaultAgentUid: string;
  // Rate limiting
  rateLimitEnabled: boolean;
  rateLimitRequests: number;
  rateLimitPeriodSeconds: number;
}

export interface Hive {
  id: string;
  name: string;
  description: string;
  agents: Agent[];
  globalUserMd: string;
  messages: Message[];
  globalFiles: FileEntry[];
  hiveMindConfig: HiveMindConfig;
  createdAt: string;
  updatedAt: string;
}

export interface HiveCreate {
  name: string;
  description?: string;
  globalUserMd?: string;
}

export interface HiveUpdate {
  name?: string;
  description?: string;
  globalUserMd?: string;
  hiveMindConfig?: HiveMindConfig;
}

export interface DashboardMetrics {
  activeNodes: number;
  totalNodes: number;
  ramUsage: number;
  ramLimit: number;
  diskUsage: number;
  diskLimit: number;
  totalTokens: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  role: string;
  password_changed: boolean;
  gateway_enabled: boolean;
}

export interface NoAuthTokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  role: string;
  password_changed: boolean;
  gateway_enabled: boolean;
}

// --- Skill Types ---
export interface Skill {
  id: string;
  name: string;
  description: string;
  type: SkillType;
  visibility: SkillVisibility;
  authorId?: string;
  organizationId?: string;
  createdAt: string;
  updatedAt: string;
  tags: string[];
  icon?: string;
  metadata: Record<string, any>;
}

export interface SkillVersion {
  id: string;
  skillId: string;
  version: string;
  code: string;
  language: string;
  entryPoint: string;
  requirements: string[];
  configSchema?: Record<string, any>;
  createdAt: string;
  isActive: boolean;
  changelog?: string;
}
