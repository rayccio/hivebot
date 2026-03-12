import React, { useState, useEffect } from 'react';
import { Hive, UserAccount, GlobalSettings, UserRole, Skill, SkillVersion, SkillType, SkillVisibility } from '../types';
import { Icons } from '../constants';
import { HiveMindDashboard } from './HiveMindDashboard';
import { AIProviderConfig } from './AIProviderConfig';
import { BridgeManager } from './BridgeManager';
import { PublicUrlConfig } from './PublicUrlConfig';
import { LoadingSpinner } from './LoadingSpinner';
import { toast } from 'react-hot-toast';
import { orchestratorService } from '../services/orchestratorService';
import { MetaBotsDashboard } from './MetaBotsDashboard';

// ---------- User Modal ----------
interface UserModalProps {
  user?: UserAccount;
  hives: Hive[];
  onClose: () => void;
  onSave: (user: {
    id?: string;
    username: string;
    password?: string;
    role: UserRole;
    assignedHiveIds: string[];
    createdAt?: string;
  }) => void;
}

const UserModal: React.FC<UserModalProps> = ({ user, hives, onClose, onSave }) => {
  const [username, setUsername] = useState(user?.username || '');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>(user?.role || UserRole.HIVE_USER);
  const [assignedHiveIds, setAssignedHiveIds] = useState<string[]>(user?.assignedHiveIds || []);
  const [loading, setLoading] = useState(false);

  const handleToggleHive = (id: string) => {
    setAssignedHiveIds(prev => 
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );
  };

  const handleSubmit = async () => {
    if (!username) {
      toast.error('Username is required');
      return;
    }
    if (!user && !password) {
      toast.error('Password is required for new users');
      return;
    }
    setLoading(true);
    try {
      await onSave({
        id: user?.id,
        username,
        password: password || user?.password,
        role,
        assignedHiveIds,
        createdAt: user?.createdAt
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 w-full max-w-md space-y-6 shadow-2xl animate-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-black uppercase tracking-tighter">{user ? 'Edit User' : 'Create User'}</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors"><Icons.X /></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Username</label>
            <input 
              type="text" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-all"
              placeholder="Enter username"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Password</label>
            <input 
              type="password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-all"
              placeholder={user ? "Leave blank to keep current" : "Enter password"}
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Role</label>
            <select 
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-all appearance-none"
              disabled={loading}
            >
              <option value={UserRole.GLOBAL_ADMIN}>Global Admin</option>
              <option value={UserRole.HIVE_ADMIN}>Hive Admin</option>
              <option value={UserRole.HIVE_USER}>Hive User</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Assigned Hives</label>
            <div className="space-y-2 max-h-40 overflow-y-auto p-2 bg-zinc-950 border border-zinc-800 rounded-xl">
              {hives.length === 0 ? (
                <p className="text-zinc-500 text-xs italic">No hives available</p>
              ) : (
                hives.map(h => (
                  <button
                    key={h.id}
                    onClick={() => handleToggleHive(h.id)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all ${
                      assignedHiveIds.includes(h.id) ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-500 hover:bg-zinc-900'
                    }`}
                    disabled={loading}
                  >
                    <span>{h.name}</span>
                    {assignedHiveIds.includes(h.id) && <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <button 
            onClick={onClose}
            className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all"
            disabled={loading}
          >
            Cancel
          </button>
          <button 
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-900/20 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Saving...</span>
              </>
            ) : (
              'Save User'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------- Skill Modal ----------
interface SkillModalProps {
  skill?: Skill;
  onClose: () => void;
  onSave: (skill: Omit<Skill, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>;
}

const SkillModal: React.FC<SkillModalProps> = ({ skill, onClose, onSave }) => {
  const [name, setName] = useState(skill?.name || '');
  const [description, setDescription] = useState(skill?.description || '');
  const [type, setType] = useState<SkillType>(skill?.type || SkillType.TOOL);
  const [visibility, setVisibility] = useState<SkillVisibility>(skill?.visibility || SkillVisibility.PRIVATE);
  const [tags, setTags] = useState<string>((skill?.tags || []).join(', '));
  const [icon, setIcon] = useState(skill?.icon || '');
  const [metadata, setMetadata] = useState(JSON.stringify(skill?.metadata || {}, null, 2));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Name is required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      let parsedMetadata = {};
      try {
        parsedMetadata = metadata ? JSON.parse(metadata) : {};
      } catch (e) {
        setError('Invalid JSON in metadata');
        setLoading(false);
        return;
      }
      await onSave({
        name,
        description,
        type,
        visibility,
        tags: tags.split(',').map(t => t.trim()).filter(t => t),
        icon: icon || undefined,
        metadata: parsedMetadata,
      });
    } catch (err: any) {
      setError(err.message || 'Failed to save skill');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 w-full max-w-2xl space-y-6 shadow-2xl animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-black uppercase tracking-tighter">{skill ? 'Edit Skill' : 'Create Skill'}</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors"><Icons.X /></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="e.g., Web Search"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="What this skill does..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as SkillType)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              >
                {Object.values(SkillType).map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Visibility</label>
              <select
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as SkillVisibility)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              >
                {Object.values(SkillVisibility).map(v => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Tags (comma separated)</label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="web, search, api"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Icon (optional)</label>
            <input
              type="text"
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="🔍 or emoji"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Metadata (JSON)</label>
            <textarea
              value={metadata}
              onChange={(e) => setMetadata(e.target.value)}
              rows={5}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder='{ "version": "1.0", "author": "..." }'
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-[10px] font-black uppercase tracking-widest text-center">
              {error}
            </div>
          )}
        </div>

        <div className="flex gap-3 pt-4">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-900/20 flex items-center justify-center gap-2"
          >
            {loading ? <LoadingSpinner size="sm" /> : skill ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------- Version Modal ----------
interface VersionModalProps {
  skillId: string;
  onClose: () => void;
  onVersionAdded: () => void;
}

const VersionModal: React.FC<VersionModalProps> = ({ skillId, onClose, onVersionAdded }) => {
  const [version, setVersion] = useState('');
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState('python');
  const [entryPoint, setEntryPoint] = useState('run');
  const [requirements, setRequirements] = useState('');
  const [configSchema, setConfigSchema] = useState('');
  const [changelog, setChangelog] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!version.trim() || !code.trim()) {
      setError('Version and code are required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      let parsedSchema = {};
      if (configSchema.trim()) {
        try {
          parsedSchema = JSON.parse(configSchema);
        } catch (e) {
          setError('Invalid JSON in config schema');
          setLoading(false);
          return;
        }
      }
      await orchestratorService.createSkillVersion(skillId, {
        version,
        code,
        language,
        entryPoint,
        requirements: requirements.split('\n').map(r => r.trim()).filter(r => r),
        configSchema: parsedSchema,
        isActive,
        changelog: changelog || undefined,
      });
      onVersionAdded();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create version');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 w-full max-w-3xl space-y-6 shadow-2xl animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-black uppercase tracking-tighter">Add New Version</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors"><Icons.X /></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Version Tag</label>
            <input
              type="text"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="e.g., 1.0.0"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Code</label>
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              rows={10}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="def run(input, config): ..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Language</label>
              <input
                type="text"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
                placeholder="python"
              />
            </div>
            <div>
              <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Entry Point</label>
              <input
                type="text"
                value={entryPoint}
                onChange={(e) => setEntryPoint(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
                placeholder="run"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Requirements (one per line)</label>
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              rows={3}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="requests==2.28.1\nbeautifulsoup4==4.12.0"
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Config Schema (JSON)</label>
            <textarea
              value={configSchema}
              onChange={(e) => setConfigSchema(e.target.value)}
              rows={3}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder='{ "apiKey": { "type": "string", "description": "API key" } }'
            />
          </div>

          <div>
            <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">Changelog</label>
            <textarea
              value={changelog}
              onChange={(e) => setChangelog(e.target.value)}
              rows={2}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
              placeholder="Added new feature..."
            />
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-zinc-800 rounded-full peer-checked:bg-emerald-600 transition-all relative">
                <div className="absolute top-1 w-3 h-3 bg-white rounded-full transition-all peer-checked:left-6 left-1"></div>
              </div>
              <span className="text-xs text-zinc-400">Active (default version)</span>
            </label>
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-[10px] font-black uppercase tracking-widest text-center">
              {error}
            </div>
          )}
        </div>

        <div className="flex gap-3 pt-4">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-900/20 flex items-center justify-center gap-2"
          >
            {loading ? <LoadingSpinner size="sm" /> : 'Add Version'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------- Main GlobalConfig ----------
interface GlobalConfigProps {
  hives: Hive[];
  users: UserAccount[];
  settings: GlobalSettings;
  onUpdateUsers: (users: UserAccount[]) => void;
  onUpdateSettings: (settings: GlobalSettings) => void;
  onCreateUser: (userData: {
    username: string;
    password: string;
    role: UserRole;
    assignedHiveIds: string[];
  }) => Promise<UserAccount>;
  onUpdateUser: (userId: string, updates: {
    username?: string;
    password?: string;
    role?: UserRole;
    assignedHiveIds?: string[];
  }) => Promise<UserAccount>;
  onDeleteUser: (userId: string) => Promise<void>;
  onToggleLoginGateway: (enabled: boolean) => Promise<void>;
  gatewayEnabled: boolean;
  currentUser: UserAccount;
  onRequirePasswordChange: (action: () => void) => void;
  onLoadUsers?: () => Promise<void>;
  onRefreshSettings: () => Promise<void>;
}

export const GlobalConfig: React.FC<GlobalConfigProps> = ({ 
  hives, 
  users, 
  settings, 
  onUpdateUsers, 
  onUpdateSettings,
  onCreateUser,
  onUpdateUser,
  onDeleteUser,
  onToggleLoginGateway,
  gatewayEnabled,
  currentUser,
  onRequirePasswordChange,
  onLoadUsers,
  onRefreshSettings
}) => {
  const [activeTab, setActiveTab] = useState<'hive-mind' | 'users' | 'environment' | 'settings' | 'logs' | 'skills' | 'meta'>('hive-mind');
  const [editingUser, setEditingUser] = useState<UserAccount | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  // Skills state
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);
  const [isCreatingSkill, setIsCreatingSkill] = useState(false);
  const [showVersionModal, setShowVersionModal] = useState<Skill | null>(null);
  const [skillVersions, setSkillVersions] = useState<Record<string, SkillVersion[]>>({});
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);

  // Load users when tab switches to users
  useEffect(() => {
    if (activeTab === 'users' && onLoadUsers) {
      setLoading(true);
      onLoadUsers().finally(() => setLoading(false));
    }
  }, [activeTab, onLoadUsers]);

  // Load skills when tab switches to skills
  useEffect(() => {
    if (activeTab === 'skills') {
      loadSkills();
    }
  }, [activeTab]);

  const loadSkills = async () => {
    setLoadingSkills(true);
    try {
      const data = await orchestratorService.listSkills();
      setSkills(data);
    } catch (err) {
      console.error('Failed to load skills', err);
      toast.error('Failed to load skills');
    } finally {
      setLoadingSkills(false);
    }
  };

  const loadVersions = async (skillId: string) => {
    try {
      const versions = await orchestratorService.listSkillVersions(skillId);
      setSkillVersions(prev => ({ ...prev, [skillId]: versions }));
    } catch (err) {
      console.error('Failed to load versions', err);
      toast.error('Failed to load versions');
    }
  };

  const toggleSkillExpand = (skillId: string) => {
    if (expandedSkill === skillId) {
      setExpandedSkill(null);
    } else {
      setExpandedSkill(skillId);
      if (!skillVersions[skillId]) {
        loadVersions(skillId);
      }
    }
  };

  const handleCreateSkill = async (skillData: Omit<Skill, 'id' | 'createdAt' | 'updatedAt'>) => {
    await orchestratorService.createSkill(skillData);
    await loadSkills();
    setIsCreatingSkill(false);
    toast.success('Skill created');
  };

  const handleUpdateSkill = async (skillId: string, updates: Partial<Skill>) => {
    await orchestratorService.updateSkill(skillId, updates);
    await loadSkills();
    setEditingSkill(null);
    toast.success('Skill updated');
  };

  const handleDeleteSkill = async (skillId: string) => {
    if (!confirm('Are you sure you want to delete this skill?')) return;
    try {
      await orchestratorService.deleteSkill(skillId);
      await loadSkills();
      toast.success('Skill deleted');
    } catch (err) {
      console.error('Failed to delete skill', err);
      toast.error('Failed to delete skill');
    }
  };

  const handleAddVersion = async (skillId: string, versionData: Omit<SkillVersion, 'id' | 'createdAt'>) => {
    await orchestratorService.createSkillVersion(skillId, versionData);
    await loadVersions(skillId);
    toast.success('Version added');
  };

  const [logs] = useState([
    { id: 1, event: 'System Boot', user: 'SYSTEM', timestamp: new Date().toISOString(), status: 'SUCCESS' },
    { id: 2, event: 'User Login', user: 'admin', timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), status: 'SUCCESS' },
    { id: 3, event: 'Hive Created', user: 'admin', timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(), status: 'SUCCESS' },
    { id: 4, event: 'Vector Sync', user: 'SYSTEM', timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(), status: 'SUCCESS' },
  ]);

  const handleSaveUser = async (user: {
    id?: string;
    username: string;
    password?: string;
    role: UserRole;
    assignedHiveIds: string[];
    createdAt?: string;
  }) => {
    setIsSaving(true);
    try {
      if (isCreating) {
        const created = await onCreateUser({
          username: user.username,
          password: user.password!,
          role: user.role,
          assignedHiveIds: user.assignedHiveIds,
        });
      } else if (editingUser) {
        const updates: {
          username?: string;
          password?: string;
          role?: UserRole;
          assignedHiveIds?: string[];
        } = {};
        if (user.username !== editingUser.username) updates.username = user.username;
        if (user.role !== editingUser.role) updates.role = user.role;
        if (user.assignedHiveIds !== editingUser.assignedHiveIds) updates.assignedHiveIds = user.assignedHiveIds;
        if (user.password && user.password !== editingUser.password) updates.password = user.password;
        
        if (Object.keys(updates).length > 0) {
          await onUpdateUser(editingUser.id, updates);
        }
      }
    } catch (err) {
      console.error('Failed to save user', err);
    } finally {
      setIsSaving(false);
      setEditingUser(null);
      setIsCreating(false);
    }
  };

  const handleCreateUser = async (userData: {
    username: string;
    password: string;
    role: UserRole;
    assignedHiveIds: string[];
  }) => {
    if (!gatewayEnabled && currentUser && !currentUser.password_changed) {
      onRequirePasswordChange(() => handleCreateUser(userData));
      return;
    }

    setIsSaving(true);
    try {
      const created = await onCreateUser(userData);
      await onRefreshSettings();
    } catch (err) {
      console.error('Failed to create user', err);
      throw err;
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteUser = async (id: string) => {
    if (confirm('Are you sure you want to delete this user?')) {
      try {
        await onDeleteUser(id);
      } catch (err) {
        console.error('Failed to delete user', err);
      }
    }
  };

  const handleToggleGateway = () => {
    if (gatewayEnabled) {
      onToggleLoginGateway(false);
    } else {
      if (!currentUser.password_changed) {
        onRequirePasswordChange(() => onToggleLoginGateway(true));
      } else {
        onToggleLoginGateway(true);
      }
    }
  };

  return (
    <div className="flex flex-col h-full animate-in fade-in duration-500">
      {/* Global Config Top Nav */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-zinc-800">
        <div className="flex items-center gap-6">
          <button 
            onClick={() => setActiveTab('hive-mind')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'hive-mind' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Hive Mind
          </button>
          <button 
            onClick={() => setActiveTab('users')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'users' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Users
          </button>
          <button 
            onClick={() => setActiveTab('environment')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'environment' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Environment
          </button>
          <button 
            onClick={() => setActiveTab('settings')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'settings' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Settings
          </button>
          <button 
            onClick={() => setActiveTab('skills')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'skills' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Skills
          </button>
          <button 
            onClick={() => setActiveTab('meta')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'meta' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Meta Bots
          </button>
          <button 
            onClick={() => setActiveTab('logs')}
            className={`text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'logs' ? 'text-emerald-400' : 'text-zinc-500 hover:text-zinc-300'}`}
          >
            Audit Logs
          </button>
        </div>
        
        <div className="flex items-center gap-3 px-4 py-1.5 bg-zinc-900/50 border border-zinc-800 rounded-xl">
          <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
          <span className="text-[9px] font-black uppercase tracking-widest text-zinc-500">Global Admin Mode</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'hive-mind' && <HiveMindDashboard hives={hives} />}
        
        {activeTab === 'users' && (
          <div className="space-y-8 max-w-5xl mx-auto">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-black tracking-tighter uppercase">User Management</h3>
                <p className="text-zinc-500 text-sm">Manage operator accounts and access levels.</p>
              </div>
              <button 
                onClick={() => setIsCreating(true)}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-900/20"
              >
                <Icons.Plus /> Create User
              </button>
            </div>

            {loading ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner />
              </div>
            ) : users.length === 0 ? (
              <div className="text-center py-12 bg-zinc-900/50 rounded-3xl border border-zinc-800">
                <p className="text-zinc-500">No users found. Create your first user.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {users.map(user => (
                  <div key={user.id} className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 relative group hover:border-emerald-500/30 transition-all">
                    <div className="flex items-center gap-4 mb-4">
                      <div className="w-12 h-12 bg-zinc-800 rounded-2xl flex items-center justify-center text-zinc-400">
                        <Icons.User />
                      </div>
                      <div>
                        <h4 className="font-bold text-zinc-200">{user.username}</h4>
                        <span className={`px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${
                          user.role === UserRole.GLOBAL_ADMIN ? 'bg-purple-500/10 text-purple-400' :
                          user.role === UserRole.HIVE_ADMIN ? 'bg-blue-500/10 text-blue-400' :
                          'bg-zinc-500/10 text-zinc-400'
                        }`}>
                          {user.role.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                    
                    <div className="space-y-3 pt-4 border-t border-zinc-800/50">
                      <div>
                        <p className="text-[9px] font-black text-zinc-500 uppercase tracking-widest mb-1">Assigned Hives</p>
                        <div className="flex flex-wrap gap-1">
                          {user.assignedHiveIds.length > 0 ? (
                            user.assignedHiveIds.map(pid => {
                              const h = hives.find(h => h.id === pid);
                              return (
                                <span key={pid} className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded text-[9px] font-bold">
                                  {h?.name || pid}
                                </span>
                              );
                            })
                          ) : (
                            <span className="text-[9px] text-zinc-600 italic">No access</span>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex justify-between text-[10px]">
                        <span className="text-zinc-500 uppercase font-bold">Created</span>
                        <span className="text-zinc-400 font-mono">
                          {user.createdAt ? new Date(user.createdAt).toLocaleDateString() : 'N/A'}
                        </span>
                      </div>
                    </div>

                    <div className="absolute top-4 right-4 flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                      <button 
                        onClick={() => setEditingUser(user)}
                        className="p-2 text-zinc-600 hover:text-white hover:bg-zinc-800 rounded-lg"
                        title="Edit User"
                      >
                        <Icons.Settings />
                      </button>
                      {user.id !== currentUser.id && (
                        <button 
                          onClick={() => handleDeleteUser(user.id)}
                          className="p-2 text-zinc-600 hover:text-red-400 hover:bg-red-500/10 rounded-lg"
                          title="Delete User"
                        >
                          <Icons.Trash />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {(isCreating || editingUser) && (
          <UserModal 
            user={editingUser || undefined}
            hives={hives}
            onClose={() => { setEditingUser(null); setIsCreating(false); }}
            onSave={handleSaveUser}
          />
        )}

        {activeTab === 'environment' && (
          <div className="max-w-5xl mx-auto space-y-12 pb-20 animate-in slide-in-from-bottom-4 duration-500">
            {/* AI Provider Configuration Box */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 space-y-6 shadow-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Cpu /></div>
              <h3 className="text-xs font-black uppercase tracking-[0.2em] text-emerald-500 mb-6">AI Provider Configuration</h3>
              <AIProviderConfig />
            </div>

            {/* Bridge Manager Box */}
            <BridgeManager />

            {/* External Communication Box */}
            <PublicUrlConfig />
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="space-y-8 max-w-3xl mx-auto">
            <div className="space-y-2">
              <h3 className="text-2xl font-black tracking-tighter uppercase">System Settings</h3>
              <p className="text-zinc-500 text-sm">Global security and behavioral parameters.</p>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 space-y-8 shadow-2xl">
              {/* Login Gateway Toggle */}
              <div className="flex items-center justify-between p-4 bg-zinc-950 border border-zinc-800 rounded-2xl">
                <div>
                  <p className="text-xs font-bold text-zinc-200">Login Gateway</p>
                  <p className="text-[10px] text-zinc-500">
                    {gatewayEnabled 
                      ? 'Multi-user secured mode. Terminate session button visible.'
                      : 'Single-user open mode. No login required. Terminate button hidden.'}
                  </p>
                </div>
                <button 
                  onClick={handleToggleGateway}
                  disabled={isSaving}
                  className={`w-12 h-6 rounded-full relative transition-all ${gatewayEnabled ? 'bg-emerald-600' : 'bg-zinc-800'} ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${gatewayEnabled ? 'left-7' : 'left-1'}`} />
                </button>
              </div>

              <div className="space-y-4">
                <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest">Session Timeout (Minutes)</label>
                <div className="flex items-center gap-4">
                  <input 
                    type="range" 
                    min="5" 
                    max="120" 
                    step="5"
                    value={settings.sessionTimeout}
                    onChange={(e) => onUpdateSettings({ ...settings, sessionTimeout: parseInt(e.target.value) })}
                    className="flex-1 accent-emerald-500"
                    disabled={!gatewayEnabled}
                  />
                  <span className="w-12 text-center font-mono text-emerald-400 font-bold">{settings.sessionTimeout}m</span>
                </div>
                <p className="text-[10px] text-zinc-500 italic">Interval before the login page is automatically reactivated due to inactivity.</p>
              </div>

              <div className="space-y-4">
                <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest">System Identity</label>
                <input 
                  type="text" 
                  value={settings.systemName}
                  onChange={(e) => onUpdateSettings({ ...settings, systemName: e.target.value })}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-all"
                  placeholder="HiveBot Orchestrator"
                />
              </div>

              <div className="space-y-4">
                <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest">Default Bot UID</label>
                <input 
                  type="text" 
                  value={settings.defaultAgentUid}
                  onChange={(e) => onUpdateSettings({ ...settings, defaultAgentUid: e.target.value })}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none transition-all"
                  placeholder="e.g. 10001"
                />
                <p className="text-[10px] text-zinc-500 italic">Newly spawned bots inherit this limited‑privilege UID for container isolation.</p>
              </div>

              <div className="flex items-center justify-between p-4 bg-zinc-950 border border-zinc-800 rounded-2xl">
                <div>
                  <p className="text-xs font-bold text-zinc-200">Maintenance Mode</p>
                  <p className="text-[10px] text-zinc-500">Restrict access to hive operations during updates.</p>
                </div>
                <button 
                  onClick={() => onUpdateSettings({ ...settings, maintenanceMode: !settings.maintenanceMode })}
                  className={`w-12 h-6 rounded-full relative transition-all ${settings.maintenanceMode ? 'bg-amber-600' : 'bg-zinc-800'}`}
                >
                  <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${settings.maintenanceMode ? 'left-7' : 'left-1'}`} />
                </button>
              </div>

              {/* Rate Limiting Section */}
              <div className="border-t border-zinc-800 pt-6">
                <h4 className="text-xs font-black uppercase tracking-widest text-emerald-500 mb-4">Rate Limiting</h4>
                
                <div className="flex items-center justify-between p-4 bg-zinc-950 border border-zinc-800 rounded-2xl mb-4">
                  <div>
                    <p className="text-xs font-bold text-zinc-200">Enable Rate Limiting</p>
                    <p className="text-[10px] text-zinc-500">Protect public endpoints from abuse (login, execute bot).</p>
                  </div>
                  <button 
                    onClick={() => onUpdateSettings({ ...settings, rateLimitEnabled: !settings.rateLimitEnabled })}
                    className={`w-12 h-6 rounded-full relative transition-all ${settings.rateLimitEnabled ? 'bg-emerald-600' : 'bg-zinc-800'}`}
                  >
                    <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${settings.rateLimitEnabled ? 'left-7' : 'left-1'}`} />
                  </button>
                </div>

                {settings.rateLimitEnabled && (
                  <div className="space-y-4 pl-4">
                    <div>
                      <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">
                        Requests per period
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="10000"
                        value={settings.rateLimitRequests}
                        onChange={(e) => onUpdateSettings({ ...settings, rateLimitRequests: parseInt(e.target.value) || 50 })}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-2">
                        Period (seconds)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="3600"
                        value={settings.rateLimitPeriodSeconds}
                        onChange={(e) => onUpdateSettings({ ...settings, rateLimitPeriodSeconds: parseInt(e.target.value) || 60 })}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
                      />
                    </div>
                    <p className="text-[9px] text-zinc-500 italic">
                      Example: 50 requests per 60 seconds = ~0.8 requests/second per IP.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="space-y-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-black tracking-tighter uppercase">Skill Library</h3>
                <p className="text-zinc-500 text-sm">Create and manage reusable skills for your bots.</p>
              </div>
              <button 
                onClick={() => setIsCreatingSkill(true)}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-900/20"
              >
                <Icons.Plus /> Create Skill
              </button>
            </div>

            {loadingSkills ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner />
              </div>
            ) : skills.length === 0 ? (
              <div className="text-center py-12 bg-zinc-900/50 rounded-3xl border border-zinc-800">
                <p className="text-zinc-500">No skills yet. Create your first skill.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {skills.map(skill => (
                  <div key={skill.id} className="bg-zinc-900 border border-zinc-800 rounded-3xl overflow-hidden">
                    <div 
                      className="p-6 cursor-pointer hover:bg-zinc-800/30 transition-colors flex items-start justify-between"
                      onClick={() => toggleSkillExpand(skill.id)}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{skill.icon || '🧩'}</span>
                          <div>
                            <h4 className="text-lg font-bold text-emerald-400">{skill.name}</h4>
                            <p className="text-sm text-zinc-400 mt-1">{skill.description}</p>
                          </div>
                        </div>
                        <div className="flex gap-4 mt-3">
                          <span className="text-[10px] px-2 py-1 bg-zinc-800 rounded-full text-zinc-400">{skill.type}</span>
                          <span className="text-[10px] px-2 py-1 bg-zinc-800 rounded-full text-zinc-400">{skill.visibility}</span>
                          {skill.tags.map(tag => (
                            <span key={tag} className="text-[10px] px-2 py-1 bg-zinc-800 rounded-full text-zinc-400">#{tag}</span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowVersionModal(skill); }}
                          className="p-2 text-zinc-500 hover:text-emerald-400 transition-colors"
                          title="Add Version"
                        >
                          <Icons.Plus />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setEditingSkill(skill); }}
                          className="p-2 text-zinc-500 hover:text-white transition-colors"
                          title="Edit Skill"
                        >
                          <Icons.Settings />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteSkill(skill.id); }}
                          className="p-2 text-zinc-500 hover:text-red-400 transition-colors"
                          title="Delete Skill"
                        >
                          <Icons.Trash />
                        </button>
                        <div className={`transform transition-transform ${expandedSkill === skill.id ? 'rotate-180' : ''}`}>
                          <svg className="w-5 h-5 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </div>

                    {expandedSkill === skill.id && (
                      <div className="border-t border-zinc-800 p-6 bg-zinc-950/50">
                        <h5 className="text-xs font-black uppercase tracking-widest text-zinc-500 mb-4">Versions</h5>
                        {skillVersions[skill.id] ? (
                          <div className="space-y-3">
                            {skillVersions[skill.id].map(version => (
                              <div key={version.id} className="bg-zinc-900 rounded-xl p-4 border border-zinc-800">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                    <span className="text-sm font-bold text-emerald-400">v{version.version}</span>
                                    {version.isActive && (
                                      <span className="text-[8px] px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded-full">active</span>
                                    )}
                                  </div>
                                  <span className="text-[10px] text-zinc-500">{new Date(version.createdAt).toLocaleDateString()}</span>
                                </div>
                                <div className="mt-2 text-xs text-zinc-400 font-mono whitespace-pre-wrap max-h-40 overflow-auto">
                                  {version.code.substring(0, 200)}...
                                </div>
                                {version.changelog && (
                                  <p className="mt-2 text-xs text-zinc-500 italic">{version.changelog}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center py-4 text-zinc-500 italic">Loading versions...</div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'meta' && (
          <MetaBotsDashboard />
        )}

        {activeTab === 'logs' && (
          <div className="space-y-8 max-w-5xl mx-auto">
            <div className="space-y-2">
              <h3 className="text-2xl font-black tracking-tighter uppercase">Audit Trail</h3>
              <p className="text-zinc-500 text-sm">Real-time system event monitoring.</p>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-3xl overflow-hidden shadow-2xl">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-zinc-950/50 border-b border-zinc-800">
                    <th className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-zinc-500">Timestamp</th>
                    <th className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-zinc-500">Event</th>
                    <th className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-zinc-500">User</th>
                    <th className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-zinc-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {logs.map(log => (
                    <tr key={log.id} className="hover:bg-zinc-800/30 transition-colors">
                      <td className="px-6 py-4 text-[10px] font-mono text-zinc-400">{new Date(log.timestamp).toLocaleString()}</td>
                      <td className="px-6 py-4 text-xs font-bold text-zinc-200">{log.event}</td>
                      <td className="px-6 py-4 text-xs text-zinc-400">{log.user}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 bg-emerald-500/10 text-emerald-500 rounded text-[9px] font-black uppercase tracking-widest">
                          {log.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Skill modals */}
      {(isCreatingSkill || editingSkill) && (
        <SkillModal
          skill={editingSkill || undefined}
          onClose={() => { setEditingSkill(null); setIsCreatingSkill(false); }}
          onSave={async (data) => {
            if (editingSkill) {
              await handleUpdateSkill(editingSkill.id, data);
            } else {
              await handleCreateSkill(data);
            }
          }}
        />
      )}

      {showVersionModal && (
        <VersionModal
          skillId={showVersionModal.id}
          onClose={() => setShowVersionModal(null)}
          onVersionAdded={() => loadVersions(showVersionModal.id)}
        />
      )}

      {isSaving && (
        <div className="fixed bottom-4 right-4 bg-emerald-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
          <LoadingSpinner size="sm" />
          <span className="text-xs">Saving...</span>
        </div>
      )}
    </div>
  );
};
