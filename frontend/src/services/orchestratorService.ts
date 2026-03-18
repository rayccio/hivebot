import { Agent, AgentCreate, AgentUpdate, FileEntry, Hive, HiveCreate, HiveUpdate, GlobalSettings, Message, UserAccount, Skill, SkillVersion, AgentSkill } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_PATH = '/api/v1';

class OrchestratorService {
  private baseUrl: string;

  constructor() {
    try {
      new URL(API_BASE_URL);
      this.baseUrl = API_BASE_URL + API_PATH;
    } catch (e) {
      console.error(`Invalid API base URL: ${API_BASE_URL}. Falling back to relative path.`);
      this.baseUrl = '/api/v1';
    }
  }

  private _authHeaders(additional?: Record<string, string>): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...additional,
    };
    const token = localStorage.getItem('hivebot_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  // ==================== AUTH ENDPOINTS ====================

  async login(username: string, password: string): Promise<{ 
    access_token: string; 
    user_id: string; 
    username: string; 
    role: string; 
    password_changed: boolean;
    gateway_enabled: boolean;
  }> {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    const res = await fetch(`${this.baseUrl}/auth/token`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Login failed');
    return res.json();
  }

  async getCurrentUser(): Promise<UserAccount> {
    const res = await fetch(`${this.baseUrl}/auth/me`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch user');
    const data = await res.json();
    return this._mapUserFromBackend(data);
  }

  async changePassword(oldPassword: string, newPassword: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/auth/change-password`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    if (!res.ok) throw new Error('Failed to change password');
  }

  async getGatewayState(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/auth/gateway-state`);
      if (!res.ok) return false;
      const data = await res.json();
      return data.enabled;
    } catch {
      return false;
    }
  }

  async getNoAuthToken(): Promise<{ 
    access_token: string; 
    user_id: string; 
    username: string; 
    role: string; 
    password_changed: boolean;
    gateway_enabled: boolean;
  }> {
    const res = await fetch(`${this.baseUrl}/auth/no-auth-token`);
    if (!res.ok) throw new Error('Failed to get no-auth token');
    return res.json();
  }

  // ==================== USER ENDPOINTS ====================

  async listUsers(): Promise<UserAccount[]> {
    const res = await fetch(`${this.baseUrl}/users`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch users');
    const data = await res.json();
    return data.map((u: any) => this._mapUserFromBackend(u));
  }

  async createUser(user: {
    username: string;
    password: string;
    role: string;
    assignedHiveIds: string[];
  }): Promise<UserAccount> {
    const payload = {
      username: user.username,
      password: user.password,
      role: user.role,
      assigned_hive_ids: user.assignedHiveIds,
    };
    const res = await fetch(`${this.baseUrl}/users`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to create user');
    const data = await res.json();
    return this._mapUserFromBackend(data);
  }

  async updateUser(userId: string, updates: {
    username?: string;
    password?: string;
    role?: string;
    assignedHiveIds?: string[];
  }): Promise<UserAccount> {
    const payload: any = {};
    if (updates.username !== undefined) payload.username = updates.username;
    if (updates.password !== undefined) payload.password = updates.password;
    if (updates.role !== undefined) payload.role = updates.role;
    if (updates.assignedHiveIds !== undefined) payload.assigned_hive_ids = updates.assignedHiveIds;
    const res = await fetch(`${this.baseUrl}/users/${userId}`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to update user');
    const data = await res.json();
    return this._mapUserFromBackend(data);
  }

  async deleteUser(userId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/users/${userId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete user');
  }

  // ==================== HIVE ENDPOINTS ====================

  async listHives(): Promise<Hive[]> {
    const res = await fetch(`${this.baseUrl}/hives`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch hives');
    return res.json();
  }

  async createHive(hive: HiveCreate): Promise<Hive> {
    const payload = {
      name: hive.name,
      description: hive.description,
      global_user_md: hive.globalUserMd,
    };
    const res = await fetch(`${this.baseUrl}/hives`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to create hive');
    return res.json();
  }

  async getHive(id: string): Promise<Hive> {
    const res = await fetch(`${this.baseUrl}/hives/${id}`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch hive');
    return res.json();
  }

  async updateHive(id: string, updates: HiveUpdate): Promise<Hive> {
    const payload: any = {};
    if (updates.name !== undefined) payload.name = updates.name;
    if (updates.description !== undefined) payload.description = updates.description;
    if (updates.globalUserMd !== undefined) payload.global_user_md = updates.globalUserMd;
    if (updates.hiveMindConfig !== undefined) payload.hive_mind_config = updates.hiveMindConfig;

    const res = await fetch(`${this.baseUrl}/hives/${id}`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to update hive');
    return res.json();
  }

  async deleteHive(id: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/hives/${id}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete hive');
  }

  // ==================== AGENT ENDPOINTS (global) ====================

  async listAgents(): Promise<Agent[]> {
    const res = await fetch(`${this.baseUrl}/agents`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch agents');
    return res.json();
  }

  async createAgent(agent: AgentCreate): Promise<Agent> {
    const res = await fetch(`${this.baseUrl}/agents`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(agent),
    });
    if (!res.ok) throw new Error('Failed to create agent');
    return res.json();
  }

  async getAgent(agentId: string): Promise<Agent> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch agent');
    return res.json();
  }

  async updateAgent(agentId: string, updates: AgentUpdate): Promise<Agent> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update agent');
    return res.json();
  }

  async deleteAgent(agentId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete agent');
  }

  async executeAgent(agentId: string, input?: string, simulation?: boolean): Promise<void> {
    let url = `${this.baseUrl}/agents/${agentId}/execute`;
    if (simulation) url += '?simulation=true';
    const res = await fetch(url, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ input }),
    });
    if (!res.ok) throw new Error('Failed to execute agent');
  }

  async addSubAgent(parentId: string, childId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/agents/${parentId}/subagents/${childId}`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to add sub‑agent');
  }

  // ==================== AGENT FILES ====================

  async uploadAgentFile(agentId: string, file: File): Promise<FileEntry> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/files`, {
      method: 'POST',
      headers: { 'Authorization': this._authHeaders().Authorization || '' },
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload file');
    return res.json();
  }

  async listAgentFiles(agentId: string): Promise<FileEntry[]> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/files`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list files');
    return res.json();
  }

  getAgentFileDownloadUrl(agentId: string, fileId: string): string {
    return `${this.baseUrl}/agents/${agentId}/files/${fileId}`;
  }

  async deleteAgentFile(agentId: string, fileId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/files/${fileId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete file');
  }

  // ==================== GLOBAL FILES ====================

  async uploadGlobalFile(file: File): Promise<FileEntry> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${this.baseUrl}/global-files`, {
      method: 'POST',
      headers: { 'Authorization': this._authHeaders().Authorization || '' },
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload global file');
    return res.json();
  }

  async listGlobalFiles(): Promise<FileEntry[]> {
    const res = await fetch(`${this.baseUrl}/global-files`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list global files');
    return res.json();
  }

  getGlobalFileDownloadUrl(filename: string): string {
    return `${this.baseUrl}/global-files/${filename}`;
  }

  async deleteGlobalFile(filename: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/global-files/${filename}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete global file');
  }

  // ==================== HIVE SPECIFIC AGENT ENDPOINTS ====================

  async listHiveAgents(hiveId: string): Promise<Agent[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/agents`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch agents');
    return res.json();
  }

  async addAgentToHive(hiveId: string, agent: Agent): Promise<Agent> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/agents`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(agent),
    });
    if (!res.ok) throw new Error('Failed to add agent to hive');
    return res.json();
  }

  async updateHiveAgent(hiveId: string, agentId: string, updates: AgentUpdate): Promise<Agent> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/agents/${agentId}`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update agent');
    return res.json();
  }

  async removeAgentFromHive(hiveId: string, agentId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/agents/${agentId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to remove agent from hive');
  }

  // ==================== MESSAGE ENDPOINTS ====================

  async listHiveMessages(hiveId: string): Promise<Message[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/messages`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch messages');
    return res.json();
  }

  async addMessageToHive(hiveId: string, message: Message): Promise<Message> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/messages`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(message),
    });
    if (!res.ok) throw new Error('Failed to add message');
    return res.json();
  }

  // ==================== GLOBAL FILES ENDPOINTS (within hive) ====================

  async listHiveGlobalFiles(hiveId: string): Promise<FileEntry[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/global-files`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch global files');
    return res.json();
  }

  async addGlobalFileToHive(hiveId: string, fileEntry: FileEntry): Promise<FileEntry> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/global-files`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(fileEntry),
    });
    if (!res.ok) throw new Error('Failed to add global file');
    return res.json();
  }

  async removeGlobalFileFromHive(hiveId: string, fileId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/global-files/${fileId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to remove global file');
  }

  // ==================== NEW: HIVE ACTIVE AGENTS ====================
  async getHiveActiveAgents(hiveId: string): Promise<Agent[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/active-agents`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch active agents');
    return res.json();
  }

  // ==================== SYSTEM ENDPOINTS ====================

  async getDefaultUid(): Promise<string> {
    const res = await fetch(`${this.baseUrl}/system/uid`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch default UID');
    const data = await res.json();
    return data.default_uid;
  }

  async setDefaultUid(uid: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/system/uid`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ default_uid: uid }),
    });
    if (!res.ok) throw new Error('Failed to set default UID');
  }

  async getPublicUrl(): Promise<string | null> {
    const res = await fetch(`${this.baseUrl}/system/public-url`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch public URL');
    const data = await res.json();
    return data.public_url;
  }

  async setPublicUrl(url: string | null): Promise<void> {
    const res = await fetch(`${this.baseUrl}/system/public-url`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ public_url: url }),
    });
    if (!res.ok) throw new Error('Failed to set public URL');
  }

  async detectPublicIp(): Promise<string | null> {
    const res = await fetch(`${this.baseUrl}/system/detect-public-ip`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to detect public IP');
    const data = await res.json();
    return data.public_ip;
  }

  async getGlobalSettings(): Promise<GlobalSettings> {
    const res = await fetch(`${this.baseUrl}/system/global-settings`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch global settings');
    return res.json();
  }

  async setGlobalSettings(settings: GlobalSettings): Promise<GlobalSettings> {
    const res = await fetch(`${this.baseUrl}/system/global-settings`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error('Failed to set global settings');
    return res.json();
  }

  // ==================== BRIDGE ENDPOINTS ====================

  async listBridges(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/bridges`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch bridges');
    return res.json();
  }

  async enableBridge(bridgeType: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/bridges/${bridgeType}/enable`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to enable bridge');
  }

  async disableBridge(bridgeType: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/bridges/${bridgeType}/disable`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to disable bridge');
  }

  async restartBridge(bridgeType: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/bridges/${bridgeType}/restart`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to restart bridge');
  }

  // ==================== PROVIDER ENDPOINTS ====================

  async getProviderConfig(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/providers`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch provider config');
    return res.json();
  }

  async getKnownProviders(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/known-providers`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch known providers');
    return res.json();
  }

  async updateProviderConfig(provider: string, updates: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/providers`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ provider, ...updates }),
    });
    if (!res.ok) throw new Error('Failed to update provider config');
    return res.json();
  }

  async deleteProvider(provider: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/providers/${provider}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete provider');
  }

  // ==================== PLANNING & TASKS ====================

  async createPlan(hiveId: string, goal: string): Promise<{ goal_id: string; tasks: any[]; edges: any[] }> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/plan`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ goal }),
    });
    if (!res.ok) throw new Error('Failed to create plan');
    return res.json();
  }

  async listTasks(hiveId: string): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/tasks`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list tasks');
    return res.json();
  }

  async assignTask(hiveId: string, taskId: string, agentId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/tasks/${taskId}/assign?agent_id=${agentId}`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to assign task');
  }

  // ==================== SKILL ENDPOINTS ====================

  async listSkills(visibility?: string, authorId?: string): Promise<Skill[]> {
    let url = `${this.baseUrl}/skills`;
    const params = new URLSearchParams();
    if (visibility) params.append('visibility', visibility);
    if (authorId) params.append('author_id', authorId);
    if (params.toString()) url += '?' + params.toString();
    const res = await fetch(url, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to list skills');
    return res.json();
  }

  async getSkill(skillId: string): Promise<Skill> {
    const res = await fetch(`${this.baseUrl}/skills/${skillId}`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get skill');
    return res.json();
  }

  async createSkill(skill: Omit<Skill, 'id' | 'createdAt' | 'updatedAt'>): Promise<Skill> {
    const res = await fetch(`${this.baseUrl}/skills`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(skill),
    });
    if (!res.ok) throw new Error('Failed to create skill');
    return res.json();
  }

  async updateSkill(skillId: string, updates: Partial<Skill>): Promise<Skill> {
    const res = await fetch(`${this.baseUrl}/skills/${skillId}`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update skill');
    return res.json();
  }

  async deleteSkill(skillId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/skills/${skillId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete skill');
  }

  // Skill versions
  async listSkillVersions(skillId: string): Promise<SkillVersion[]> {
    const res = await fetch(`${this.baseUrl}/skills/${skillId}/versions`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to list versions');
    return res.json();
  }

  async createSkillVersion(skillId: string, version: Omit<SkillVersion, 'id' | 'createdAt'>): Promise<SkillVersion> {
    const res = await fetch(`${this.baseUrl}/skills/${skillId}/versions`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(version),
    });
    if (!res.ok) throw new Error('Failed to create version');
    return res.json();
  }

  async getSkillVersion(versionId: string): Promise<SkillVersion> {
    const res = await fetch(`${this.baseUrl}/skills/versions/${versionId}`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get version');
    return res.json();
  }

  async updateSkillVersion(versionId: string, updates: Partial<SkillVersion>): Promise<SkillVersion> {
    const res = await fetch(`${this.baseUrl}/skills/versions/${versionId}`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error('Failed to update version');
    return res.json();
  }

  // Agent skills
  async listAgentSkills(agentId: string): Promise<AgentSkill[]> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/skills`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to list agent skills');
    return res.json();
  }

  async installSkill(agentId: string, skillId: string, versionId?: string, config?: Record<string, any>): Promise<AgentSkill> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/skills/${skillId}/install`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify({ version_id: versionId, config }),
    });
    if (!res.ok) throw new Error('Failed to install skill');
    return res.json();
  }

  async uninstallSkill(agentId: string, skillId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/skills/${skillId}/uninstall`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to uninstall skill');
  }

  async updateSkillConfig(agentId: string, skillId: string, config: Record<string, any>): Promise<AgentSkill> {
    const res = await fetch(`${this.baseUrl}/agents/${agentId}/skills/${skillId}/config`, {
      method: 'PATCH',
      headers: this._authHeaders(),
      body: JSON.stringify({ config }),
    });
    if (!res.ok) throw new Error('Failed to update skill config');
    return res.json();
  }

  // ==================== SKILL SUGGESTIONS ====================

  async listSkillSuggestions(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/skills/suggestions`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list skill suggestions');
    return res.json();
  }

  async createSkillFromSuggestion(suggestionId: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/skills/suggestions/${suggestionId}/create-skill`, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to create skill from suggestion');
    return res.json();
  }

  async deleteSkillSuggestion(suggestionId: string): Promise<void> {
    const res = await fetch(`${this.baseUrl}/skills/suggestions/${suggestionId}`, {
      method: 'DELETE',
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete suggestion');
  }

  // ==================== META ENDPOINTS ====================

  async getMetaStatus(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/meta/status`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get meta status');
    return res.json();
  }

  async getTestAgents(limit?: number): Promise<any[]> {
    let url = `${this.baseUrl}/meta/test-agents`;
    if (limit) url += `?limit=${limit}`;
    const res = await fetch(url, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get test agents');
    return res.json();
  }

  async getMetaPerformance(hours: number = 24): Promise<any> {
    const res = await fetch(`${this.baseUrl}/meta/performance?hours=${hours}`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get meta performance');
    return res.json();
  }

  async getAgentMetrics(agentId: string, hours: number = 24): Promise<any> {
    const res = await fetch(`${this.baseUrl}/meta/metrics/agent/${agentId}?hours=${hours}`, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get agent metrics');
    return res.json();
  }

  async listABTests(limit?: number): Promise<any[]> {
    let url = `${this.baseUrl}/meta/ab-tests`;
    if (limit) url += `?limit=${limit}`;
    const res = await fetch(url, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to list A/B tests');
    return res.json();
  }

  async getMetaLogs(limit?: number): Promise<any[]> {
    let url = `${this.baseUrl}/meta/logs`;
    if (limit) url += `?limit=${limit}`;
    const res = await fetch(url, { headers: this._authHeaders() });
    if (!res.ok) throw new Error('Failed to get meta logs');
    return res.json();
  }

  // ==================== GOALS ENDPOINTS ====================

  async listGoals(hiveId: string): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/goals`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list goals');
    return res.json();
  }

  async createGoal(hiveId: string, goal: { description: string; constraints?: any; success_criteria?: string[] }): Promise<any> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/goals`, {
      method: 'POST',
      headers: this._authHeaders(),
      body: JSON.stringify(goal),
    });
    if (!res.ok) throw new Error('Failed to create goal');
    return res.json();
  }

  async listTasksForGoal(hiveId: string, goalId: string): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/goals/${goalId}/tasks`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list tasks');
    return res.json();
  }

  async listArtifacts(hiveId: string, goalId: string): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/hives/${hiveId}/goals/${goalId}/artifacts`, {
      headers: this._authHeaders(),
    });
    if (!res.ok) throw new Error('Failed to list artifacts');
    return res.json();
  }

  getArtifactDownloadUrl(hiveId: string, goalId: string, artifactId: string): string {
    return `${this.baseUrl}/hives/${hiveId}/goals/${goalId}/artifacts/${artifactId}`;
  }

  // ==================== PRIVATE HELPERS ====================

  private _mapUserFromBackend(data: any): UserAccount {
    return {
      id: data.id,
      username: data.username,
      role: data.role,
      assignedHiveIds: data.assigned_hive_ids || [],
      lastLogin: data.last_login,
      createdAt: data.created_at,
      updatedAt: data.updated_at,
      password_changed: data.password_changed,
    };
  }
}

export const orchestratorService = new OrchestratorService();
