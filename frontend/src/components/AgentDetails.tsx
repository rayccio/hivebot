import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Agent, AgentStatus, Message, FileEntry, ReportingTarget, ChannelConfig, ChannelCredentials, Skill, SkillVersion } from '../types';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';
import { useProviders } from '../contexts/ProviderContext';
import { useBridges } from '../contexts/BridgeContext';
import { LoadingSpinner } from './LoadingSpinner';
import { SkillLibrary } from './SkillLibrary';
import { toast } from 'react-hot-toast';

interface AgentDetailsProps {
  agent: Agent;
  onUpdate: (updated: Agent) => Promise<Agent>;
  onRun: () => void;
  onDelete: (id: string) => void;
  messages: Message[];
  allAgents: Agent[];
  globalFiles: FileEntry[];
}

export const AgentDetails: React.FC<AgentDetailsProps> = ({ agent, onUpdate, onRun, onDelete, messages, allAgents, globalFiles }) => {
  const [activeTab, setActiveTab] = useState<'soul' | 'identity' | 'tools' | 'files' | 'channels' | 'config' | 'logs' | 'subagents' | 'skills'>('soul');
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [editingChannel, setEditingChannel] = useState<string | null>(null);
  const [editChannelData, setEditChannelData] = useState<ChannelConfig | null>(null);
  const [selectedChildId, setSelectedChildId] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { providers, getEnabledModels, getPrimaryModel, getUtilityModel, loading: providersLoading } = useProviders();
  const { enabledBridgeTypes } = useBridges();
  const [modelsVersion, setModelsVersion] = useState(0);
  const [installedSkills, setInstalledSkills] = useState(agent.skills || []);
  const [showSkillLibrary, setShowSkillLibrary] = useState(false);
  const [skillVersions, setSkillVersions] = useState<Record<string, SkillVersion[]>>({});

  // Local state for editable fields
  const [localName, setLocalName] = useState(agent.name);
  const [localRole, setLocalRole] = useState(agent.role);
  const [localSoulMd, setLocalSoulMd] = useState(agent.soulMd);
  const [localIdentityMd, setLocalIdentityMd] = useState(agent.identityMd);
  const [localToolsMd, setLocalToolsMd] = useState(agent.toolsMd);
  const [localParentId, setLocalParentId] = useState(agent.parentId);
  const [localReasoning, setLocalReasoning] = useState(agent.reasoning);
  const [localReportingTarget, setLocalReportingTarget] = useState(agent.reportingTarget || ReportingTarget.PARENT);
  const [localSubAgentIds, setLocalSubAgentIds] = useState(agent.subAgentIds || []);
  const [localChannels, setLocalChannels] = useState<ChannelConfig[]>(agent.channels || []);

  const primaryModel = useMemo(() => {
    const prim = getPrimaryModel();
    return prim ? `${prim.provider}:${prim.modelId}` : null;
  }, [providers, getPrimaryModel]);

  const utilityModel = useMemo(() => {
    const util = getUtilityModel();
    return util ? `${util.provider}:${util.modelId}` : null;
  }, [providers, getUtilityModel]);

  useEffect(() => {
    setLocalName(agent.name);
    setLocalRole(agent.role);
    setLocalSoulMd(agent.soulMd);
    setLocalIdentityMd(agent.identityMd);
    setLocalToolsMd(agent.toolsMd);
    setLocalParentId(agent.parentId);
    setLocalReasoning(agent.reasoning);
    setLocalReportingTarget(agent.reportingTarget || ReportingTarget.PARENT);
    setLocalSubAgentIds(agent.subAgentIds || []);
    setLocalChannels(agent.channels || []);
    setInstalledSkills(agent.skills || []);
  }, [agent]);

  // Load versions for installed skills
  useEffect(() => {
    installedSkills.forEach(async (as) => {
      if (!skillVersions[as.skillId]) {
        try {
          const versions = await orchestratorService.listSkillVersions(as.skillId);
          setSkillVersions(prev => ({ ...prev, [as.skillId]: versions }));
        } catch (err) {
          console.error('Failed to load skill versions', err);
        }
      }
    });
  }, [installedSkills]);

  const handleUpdate = useCallback(async (updates: Partial<Agent>) => {
    setIsSaving(true);
    try {
      const updated = { ...agent, ...updates };
      await onUpdate(updated);
    } catch (err) {
      console.error('Update failed', err);
    } finally {
      setIsSaving(false);
    }
  }, [agent, onUpdate]);

  const handleNameBlur = useCallback(async () => {
    if (localName === agent.name) return;
    await handleUpdate({ name: localName });
  }, [localName, agent.name, handleUpdate]);

  const handleRoleBlur = useCallback(async () => {
    if (localRole === agent.role) return;
    await handleUpdate({ role: localRole });
  }, [localRole, agent.role, handleUpdate]);

  const handleSoulBlur = useCallback(async () => {
    if (localSoulMd === agent.soulMd) return;
    await handleUpdate({ soulMd: localSoulMd });
  }, [localSoulMd, agent.soulMd, handleUpdate]);

  const handleIdentityBlur = useCallback(async () => {
    if (localIdentityMd === agent.identityMd) return;
    await handleUpdate({ identityMd: localIdentityMd });
  }, [localIdentityMd, agent.identityMd, handleUpdate]);

  const handleToolsBlur = useCallback(async () => {
    if (localToolsMd === agent.toolsMd) return;
    await handleUpdate({ toolsMd: localToolsMd });
  }, [localToolsMd, agent.toolsMd, handleUpdate]);

  const handleParentChange = useCallback(async (value: string | undefined) => {
    setLocalParentId(value);
    await handleUpdate({ parentId: value });
  }, [handleUpdate]);

  const handleReportingTargetChange = useCallback(async (value: ReportingTarget) => {
    setLocalReportingTarget(value);
    await handleUpdate({ reportingTarget: value });
  }, [handleUpdate]);

  const handleReasoningChange = useCallback(async (updates: Partial<typeof agent.reasoning>) => {
    const newReasoning = { ...localReasoning, ...updates };
    setLocalReasoning(newReasoning);
    await handleUpdate({ reasoning: newReasoning });
  }, [localReasoning, handleUpdate]);

  const handleTemperatureBlur = useCallback(async (e: React.FocusEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (isNaN(val) || val === agent.reasoning.temperature) return;
    await handleReasoningChange({ temperature: val });
  }, [agent.reasoning.temperature, handleReasoningChange]);

  const handleTopPBlur = useCallback(async (e: React.FocusEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (isNaN(val) || val === agent.reasoning.topP) return;
    await handleReasoningChange({ topP: val });
  }, [agent.reasoning.topP, handleReasoningChange]);

  const handleMaxTokensBlur = useCallback(async (e: React.FocusEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    if (isNaN(val) || val === agent.reasoning.maxTokens) return;
    await handleReasoningChange({ maxTokens: val });
  }, [agent.reasoning.maxTokens, handleReasoningChange]);

  const handleModelChange = useCallback(async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const model = e.target.value;
    await handleReasoningChange({ model });
  }, [handleReasoningChange]);

  const handleCheapModelChange = useCallback(async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const cheap_model = e.target.value || undefined;
    await handleReasoningChange({ cheap_model });
  }, [handleReasoningChange]);

  const handleGlobalDefaultToggle = useCallback(async (useGlobal: boolean) => {
    await handleReasoningChange({ use_global_default: useGlobal });
  }, [handleReasoningChange]);

  const handleCustomMaxTokensToggle = useCallback(async (useCustom: boolean) => {
    await handleReasoningChange({ use_custom_max_tokens: useCustom });
  }, [handleReasoningChange]);

  const handleAddChannel = useCallback((type: ChannelConfig['type']) => {
    const newChannel: ChannelConfig = {
      id: `ch-${Math.random().toString(36).substr(2, 5)}`,
      type,
      enabled: false,
      credentials: {},
      status: 'disconnected'
    };
    const updatedChannels = [...localChannels, newChannel];
    setLocalChannels(updatedChannels);
    handleUpdate({ channels: updatedChannels });
    setEditingChannel(newChannel.id);
    setEditChannelData(newChannel);
  }, [localChannels, handleUpdate]);

  const handleSelectChannel = useCallback((channelId: string) => {
    const channel = localChannels.find(c => c.id === channelId);
    if (channel) {
      setEditChannelData({ ...channel, credentials: { ...channel.credentials } });
      setEditingChannel(channelId);
    }
  }, [localChannels]);

  const handleEditFieldChange = useCallback((field: keyof ChannelCredentials, value: string) => {
    if (!editChannelData) return;
    setEditChannelData({
      ...editChannelData,
      credentials: {
        ...editChannelData.credentials,
        [field]: value
      }
    });
  }, [editChannelData]);

  const handleSaveChannel = useCallback(async () => {
    if (!editChannelData) return;
    const updatedChannels = localChannels.map(ch =>
      ch.id === editChannelData.id ? editChannelData : ch
    );
    setLocalChannels(updatedChannels);
    await handleUpdate({ channels: updatedChannels });
    setEditingChannel(null);
    setEditChannelData(null);
  }, [editChannelData, localChannels, handleUpdate]);

  const handleCancelEdit = useCallback(() => {
    setEditingChannel(null);
    setEditChannelData(null);
  }, []);

  const handleDeleteChannel = useCallback(async (id: string) => {
    const updatedChannels = localChannels.filter(c => c.id !== id);
    setLocalChannels(updatedChannels);
    await handleUpdate({ channels: updatedChannels });
    if (editingChannel === id) {
      setEditingChannel(null);
      setEditChannelData(null);
    }
  }, [localChannels, handleUpdate, editingChannel]);

  const handleAddSubAgent = useCallback(async () => {
    if (!selectedChildId) return;
    try {
      await orchestratorService.addSubAgent(agent.id, selectedChildId);
      const updatedSubAgents = [...localSubAgentIds, selectedChildId];
      setLocalSubAgentIds(updatedSubAgents);
      await handleUpdate({ subAgentIds: updatedSubAgents });
      setSelectedChildId('');
    } catch (err) {
      console.error('Failed to add sub-agent', err);
    }
  }, [selectedChildId, agent.id, localSubAgentIds, handleUpdate]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      const newFile = await orchestratorService.uploadAgentFile(agent.id, file);
      const updatedAgent = await orchestratorService.getAgent(agent.id);
      setLocalSubAgentIds(updatedAgent.subAgentIds || []);
      await handleUpdate(updatedAgent);
    } catch (err) {
      console.error('File upload failed', err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!confirm('Delete this file?')) return;
    try {
      await orchestratorService.deleteAgentFile(agent.id, fileId);
      const updatedAgent = await orchestratorService.getAgent(agent.id);
      await handleUpdate(updatedAgent);
    } catch (err) {
      console.error('File deletion failed', err);
    }
  };

  const handleDeleteAgent = () => {
    if (confirm(`Are you sure you want to delete bot "${agent.name}"?`)) {
      onDelete(agent.id);
    }
  };

  // Skill handling
  const handleInstallSkill = async (skill: Skill) => {
    try {
      const agentSkill = await orchestratorService.installSkill(agent.id, skill.id);
      setInstalledSkills(prev => [...prev, agentSkill]);
      toast.success(`Skill ${skill.name} installed`);
      setShowSkillLibrary(false);
    } catch (err) {
      console.error('Failed to install skill', err);
      toast.error('Failed to install skill');
    }
  };

  const handleUninstallSkill = async (skillId: string) => {
    if (!confirm('Uninstall this skill?')) return;
    try {
      await orchestratorService.uninstallSkill(agent.id, skillId);
      setInstalledSkills(prev => prev.filter(s => s.skillId !== skillId));
      toast.success('Skill uninstalled');
    } catch (err) {
      console.error('Failed to uninstall skill', err);
      toast.error('Failed to uninstall skill');
    }
  };

  useEffect(() => {
    setModelsVersion(v => v + 1);
  }, [providers]);

  const availableModels = useMemo(() => getEnabledModels(), [modelsVersion, getEnabledModels]);

  const memoryLoad = agent.memory?.shortTerm?.length ? ((agent.memory.shortTerm.length / 10) * 100).toFixed(0) : '0';

  const editingFile = agent.localFiles?.find(f => f.id === selectedFileId) || globalFiles.find(f => f.id === selectedFileId);
  const isGlobalFile = globalFiles.some(f => f.id === selectedFileId);

  const availableChannelTypes = useMemo(() => {
    const types = [...enabledBridgeTypes];
    if (!types.includes('custom')) types.push('custom');
    return types;
  }, [enabledBridgeTypes]);

  if (!agent) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-20">
      <div className="flex items-start justify-between bg-zinc-900/50 p-6 rounded-3xl border border-zinc-800 shadow-2xl">
        <div className="flex items-center gap-6 flex-1">
          <div className="w-20 h-20 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-center justify-center text-emerald-500 shadow-inner flex-shrink-0 relative overflow-hidden">
            <Icons.Cpu />
          </div>
          <div className="flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={localName}
                onChange={(e) => setLocalName(e.target.value)}
                onBlur={handleNameBlur}
                className="text-3xl font-black bg-transparent border-none focus:outline-none hover:bg-zinc-800 rounded px-2 -ml-2 w-full transition-colors tracking-tighter text-zinc-100"
              />
              {isSaving && (
                <div className="w-4 h-4">
                  <LoadingSpinner size="sm" />
                </div>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] px-2 py-1 bg-zinc-800 text-zinc-400 rounded-md border border-zinc-700 font-mono">Bot ID: {agent.id}</span>
              <span className={`text-[10px] px-2 py-1 rounded-md uppercase font-black tracking-widest ${agent.status === AgentStatus.RUNNING ? 'bg-emerald-500/20 text-emerald-400 animate-pulse' : 'bg-zinc-800 text-zinc-500'}`}>{agent.status}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDeleteAgent}
            className="p-4 bg-red-600/20 text-red-500 rounded-2xl hover:bg-red-600/30 transition-all"
            title="Delete Bot"
          >
            <Icons.Trash className="w-5 h-5" />
          </button>
          <button
            onClick={onRun}
            disabled={agent.status === AgentStatus.RUNNING}
            className="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-2xl font-black uppercase tracking-widest text-xs transition-all shadow-2xl flex items-center gap-3"
          >
            {agent.status === AgentStatus.RUNNING ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Executing...</span>
              </>
            ) : (
              <>
                <Icons.Terminal />
                <span>Execute Bot</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 p-1 bg-zinc-900 rounded-2xl border border-zinc-800 w-fit overflow-x-auto max-w-full">
        {(['soul', 'identity', 'tools', 'files', 'channels', 'config', 'logs', 'subagents', 'skills'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2 text-[10px] font-black uppercase tracking-widest transition-all rounded-xl whitespace-nowrap ${activeTab === tab ? 'bg-zinc-800 text-emerald-400 shadow-lg' : 'text-zinc-500 hover:text-zinc-300'}`}>
            {tab === 'files' ? 'Bot Files' : tab === 'soul' ? 'Soul.md' : tab === 'identity' ? 'Identity.md' : tab === 'tools' ? 'Tools.md' : tab === 'subagents' ? 'Sub‑Bots' : tab}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-3">
          {/* Soul, Identity, Tools tabs (unchanged) */}
          {activeTab === 'soul' && (
            <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-2xl">
              <textarea
                value={localSoulMd}
                onChange={(e) => setLocalSoulMd(e.target.value)}
                onBlur={handleSoulBlur}
                className="w-full h-[550px] bg-transparent text-zinc-300 font-mono text-sm resize-none focus:outline-none"
                spellCheck={false}
              />
            </div>
          )}
          {activeTab === 'identity' && (
            <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-2xl">
              <textarea
                value={localIdentityMd}
                onChange={(e) => setLocalIdentityMd(e.target.value)}
                onBlur={handleIdentityBlur}
                className="w-full h-[550px] bg-transparent text-zinc-300 font-mono text-sm resize-none focus:outline-none"
                spellCheck={false}
              />
            </div>
          )}
          {activeTab === 'tools' && (
            <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-2xl">
              <textarea
                value={localToolsMd}
                onChange={(e) => setLocalToolsMd(e.target.value)}
                onBlur={handleToolsBlur}
                className="w-full h-[550px] bg-transparent text-zinc-300 font-mono text-sm resize-none focus:outline-none"
                spellCheck={false}
              />
            </div>
          )}

          {/* Channels Tab (unchanged) */}
          {activeTab === 'channels' && (
            <div className="h-[600px] flex flex-col space-y-4 animate-in fade-in duration-300">
              <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
                {availableChannelTypes.map((type) => (
                  <button
                    key={type}
                    onClick={() => handleAddChannel(type as any)}
                    className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-[10px] font-black uppercase tracking-widest text-zinc-500 hover:text-emerald-400 transition-all shrink-0"
                  >
                    Add {type}
                  </button>
                ))}
              </div>
              <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-4 space-y-2 overflow-y-auto">
                  {localChannels.length === 0 && <p className="text-zinc-600 text-xs italic p-4">No active relay channels.</p>}
                  {localChannels.map(ch => (
                    <button
                      key={ch.id}
                      onClick={() => handleSelectChannel(ch.id)}
                      className={`w-full text-left p-4 rounded-2xl border transition-all flex items-center justify-between ${editingChannel === ch.id ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-zinc-950 border-zinc-800 text-zinc-500 hover:bg-zinc-900'}`}
                    >
                      <div className="flex items-center gap-3">
                        <Icons.Globe />
                        <span className="text-[10px] font-black uppercase tracking-widest">{ch.type}</span>
                      </div>
                      <div className={`w-1.5 h-1.5 rounded-full ${ch.enabled ? 'bg-emerald-500' : 'bg-zinc-700'}`} />
                    </button>
                  ))}
                </div>
                <div className="md:col-span-2 bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-2xl overflow-y-auto">
                  {editingChannel && editChannelData ? (
                    <div className="space-y-6">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-black uppercase tracking-widest text-emerald-500">Configure: {editChannelData.type}</h4>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <span className="text-[10px] font-black text-zinc-500 uppercase">Status</span>
                          <input
                            type="checkbox"
                            checked={editChannelData.enabled}
                            onChange={e => {
                              setEditChannelData({ ...editChannelData, enabled: e.target.checked });
                            }}
                            className="sr-only peer"
                          />
                          <div className="w-10 h-5 bg-zinc-800 rounded-full peer-checked:bg-emerald-600 transition-all relative">
                            <div className="absolute top-1 left-1 w-3 h-3 bg-white rounded-full transition-all peer-checked:left-6"></div>
                          </div>
                        </label>
                      </div>
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-2">Bot Token / API Key</label>
                            <input
                              type="password"
                              value={editChannelData.credentials?.botToken || ''}
                              onChange={e => handleEditFieldChange('botToken', e.target.value)}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-xs text-zinc-300"
                              placeholder="Relay Credentials"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] font-bold text-zinc-600 uppercase mb-2">Channel / Chat ID</label>
                            <input
                              type="text"
                              value={editChannelData.credentials?.chatId || ''}
                              onChange={e => handleEditFieldChange('chatId', e.target.value)}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-xs text-zinc-300"
                              placeholder="@target_channel"
                            />
                          </div>
                        </div>
                      </div>
                      <div className="pt-6 border-t border-zinc-800 flex justify-between items-center">
                        <button onClick={handleCancelEdit} className="text-[10px] font-black uppercase text-zinc-500">Close</button>
                        <button
                          onClick={handleSaveChannel}
                          className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-emerald-500 transition-colors"
                        >
                          Save
                        </button>
                        <button onClick={() => handleDeleteChannel(editChannelData.id)} className="text-[10px] font-black uppercase text-red-500/50 hover:text-red-500">Destroy Relay</button>
                      </div>
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center text-zinc-600 italic">Select a relay channel to manage.</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Config Tab (unchanged) */}
          {activeTab === 'config' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-8 space-y-6 shadow-xl">
                <h3 className="text-xs font-black uppercase tracking-widest text-emerald-500">Reasoning Engine</h3>

                <div>
                  <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Role</label>
                  <input
                    type="text"
                    value={localRole}
                    onChange={(e) => setLocalRole(e.target.value)}
                    onBlur={handleRoleBlur}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200"
                    placeholder="e.g. Chief of Staff, Worker"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Reporting Target</label>
                  <select
                    value={localReportingTarget}
                    onChange={(e) => handleReportingTargetChange(e.target.value as ReportingTarget)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200"
                  >
                    <option value={ReportingTarget.PARENT}>Report to Parent Bot</option>
                    <option value={ReportingTarget.OWNER_DIRECT}>Direct to Owner (Channels)</option>
                    <option value={ReportingTarget.BOTH}>Hybrid Reporting</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-4 bg-zinc-950 rounded-xl border border-zinc-800">
                  <div>
                    <span className="text-sm font-medium text-zinc-300">Model Selection</span>
                    <p className="text-[10px] text-zinc-500 mt-1">
                      {localReasoning?.use_global_default
                        ? `Using global primary: ${primaryModel ? primaryModel : 'not configured'}`
                        : 'Using custom model'}
                    </p>
                    {localReasoning?.use_global_default && (
                      <p className="text-[10px] text-zinc-500 mt-1">
                        Global utility: {utilityModel ? utilityModel : 'not configured'}
                      </p>
                    )}
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      className="sr-only peer"
                      checked={!localReasoning?.use_global_default}
                      onChange={(e) => handleGlobalDefaultToggle(!e.target.checked)}
                    />
                    <div className="w-11 h-6 bg-zinc-700 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                    <span className="ml-3 text-xs font-medium text-zinc-300">
                      {localReasoning?.use_global_default ? 'Default' : 'Custom'}
                    </span>
                  </label>
                </div>

                {!localReasoning?.use_global_default && (
                  <div className="space-y-4 mt-4">
                    <div>
                      <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Model</label>
                      <select
                        key={modelsVersion}
                        value={localReasoning?.model || ''}
                        onChange={handleModelChange}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500/50 outline-none"
                      >
                        <option value="">Select a model</option>
                        {providersLoading && (
                          <option value="" disabled>Loading models...</option>
                        )}
                        {!providersLoading && availableModels.length === 0 && (
                          <option value="" disabled>No enabled models found. Configure providers in Environment.</option>
                        )}
                        {availableModels.map(({ provider, providerDisplay, modelId, modelName }) => (
                          <option key={`${provider}:${modelId}`} value={`${provider}:${modelId}`}>
                            {providerDisplay}: {modelName}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Cheap Model Selector */}
                    <div>
                      <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Cheap Model (for summarisation, optional)</label>
                      <select
                        value={localReasoning?.cheap_model || ''}
                        onChange={handleCheapModelChange}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500/50 outline-none"
                      >
                        <option value="">Use Global Utility</option>
                        {availableModels.map(({ provider, providerDisplay, modelId, modelName }) => (
                          <option key={`cheap-${provider}:${modelId}`} value={`${provider}:${modelId}`}>
                            {providerDisplay}: {modelName}
                          </option>
                        ))}
                      </select>
                      <p className="text-[10px] text-zinc-500 mt-1">
                        Used for background memory summarisation to save tokens. Leave empty to use the global utility model.
                      </p>
                    </div>

                    <div className="mt-4 border-t border-zinc-800 pt-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-zinc-300">Max Tokens</span>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            className="sr-only peer"
                            checked={localReasoning?.use_custom_max_tokens}
                            onChange={(e) => handleCustomMaxTokensToggle(e.target.checked)}
                          />
                          <div className="w-11 h-6 bg-zinc-700 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                          <span className="ml-3 text-xs font-medium text-zinc-300">
                            {localReasoning?.use_custom_max_tokens ? 'Custom' : 'Default'}
                          </span>
                        </label>
                      </div>
                      {localReasoning?.use_custom_max_tokens && (
                        <div className="mt-2">
                          <input
                            type="number"
                            min="1"
                            max="4096"
                            value={localReasoning?.maxTokens || 150}
                            onChange={(e) => setLocalReasoning({ ...localReasoning, maxTokens: parseInt(e.target.value, 10) })}
                            onBlur={handleMaxTokensBlur}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200"
                          />
                          <p className="text-[10px] text-zinc-500 mt-1">
                            Maximum number of tokens in the response. When default, the model's default maximum is used.
                          </p>
                        </div>
                      )}
                    </div>

                    <div>
                      <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Temperature</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={localReasoning?.temperature || 0.7}
                        onChange={(e) => setLocalReasoning({ ...localReasoning, temperature: parseFloat(e.target.value) })}
                        onBlur={handleTemperatureBlur}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Top P</label>
                      <input
                        type="number"
                        step="0.05"
                        min="0"
                        max="1"
                        value={localReasoning?.topP || 1.0}
                        onChange={(e) => setLocalReasoning({ ...localReasoning, topP: parseFloat(e.target.value) })}
                        onBlur={handleTopPBlur}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-8 space-y-6 shadow-xl">
                <h3 className="text-xs font-black uppercase tracking-widest text-emerald-500">Security & Isolation</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-[10px] font-black text-zinc-600 uppercase mb-2">Parent Bot ID</label>
                    <select
                      value={localParentId || ''}
                      onChange={(e) => handleParentChange(e.target.value || undefined)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200"
                    >
                      <option value="">None (Root Bot)</option>
                      {allAgents.filter(a => a.id !== agent.id).map(a => (
                        <option key={a.id} value={a.id}>{a.name} ({a.id})</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Bot Files Tab (renamed) */}
          {activeTab === 'files' && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 h-[600px] animate-in fade-in duration-300">
              <div className="md:col-span-1 bg-zinc-900 rounded-3xl border border-zinc-800 p-4 space-y-6 flex flex-col overflow-hidden">
                <div className="space-y-4 flex-1 overflow-y-auto">
                  <div className="flex items-center justify-between px-2">
                    <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Bot Files</span>
                    <button 
                      onClick={() => fileInputRef.current?.click()} 
                      disabled={isUploading}
                      className="text-emerald-500 hover:text-emerald-400 disabled:opacity-50"
                    >
                      {isUploading ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <Icons.Plus />
                      )}
                    </button>
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      onChange={handleFileUpload} 
                      className="hidden" 
                    />
                  </div>
                  <div className="space-y-1">
                    {agent.localFiles?.map(file => (
                      <div key={file.id} className="flex items-center justify-between p-2 rounded-xl border border-zinc-800 bg-zinc-950">
                        <button 
                          onClick={() => setSelectedFileId(file.id)}
                          className={`flex-1 text-left truncate text-[11px] font-bold ${selectedFileId === file.id && !isGlobalFile ? 'text-emerald-400' : 'text-zinc-500'}`}
                        >
                          <Icons.File className="inline mr-2" /> {file.name}
                        </button>
                        <button 
                          onClick={() => handleDeleteFile(file.id)}
                          className="text-red-500/50 hover:text-red-500 ml-2"
                        >
                          <Icons.Trash className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="md:col-span-3 bg-zinc-900 rounded-3xl border border-zinc-800 p-6 flex flex-col shadow-2xl relative">
                {editingFile ? (
                  <div className="flex-1 flex flex-col">
                    <div className="flex justify-between items-center mb-2">
                      <h4 className="text-sm font-bold">{editingFile.name}</h4>
                      <a 
                        href={orchestratorService.getAgentFileDownloadUrl(agent.id, editingFile.id)} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-emerald-500 hover:text-emerald-400 text-xs"
                      >
                        Download
                      </a>
                    </div>
                    {editingFile.type === 'md' || editingFile.type === 'txt' ? (
                      <textarea 
                        value={editingFile.content} 
                        readOnly={isGlobalFile}
                        className="flex-1 w-full bg-zinc-950 border border-zinc-800 rounded-2xl p-4 text-sm font-mono text-zinc-300 resize-none outline-none"
                        spellCheck={false}
                      />
                    ) : (
                      <div className="flex-1 flex items-center justify-center text-zinc-500">
                        Preview not available
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-zinc-600 italic">
                    Select a file to preview
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Logs Tab (unchanged) */}
          {activeTab === 'logs' && (
            <div className="bg-zinc-950 rounded-3xl border border-zinc-800 overflow-hidden flex flex-col h-[600px] shadow-2xl animate-in zoom-in duration-300">
              <div className="p-4 bg-zinc-900/50 border-b border-zinc-800 flex items-center justify-between">
                <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Hive Standard Output</span>
                <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div><span className="text-[9px] text-emerald-500 font-black tracking-widest uppercase">Live Stream</span></div>
              </div>
              <div className="flex-1 overflow-y-auto p-6 space-y-3 font-mono text-[12px]">
                {messages.length === 0 && <p className="text-zinc-600 italic text-center py-10">Waiting for next execution cycle...</p>}
                {messages.map(msg => (
                  <div key={msg.id} className={`flex gap-4 border-l-2 pl-4 py-2 ${msg.type === 'error' ? 'text-red-400 border-red-500/50' : msg.type === 'internal' ? 'text-zinc-500 border-zinc-800' : msg.type === 'chat' ? 'text-emerald-300 border-emerald-500/30' : 'text-zinc-400 border-zinc-800'}`}>
                    <span className="opacity-30 whitespace-nowrap text-[10px]">[{new Date(msg.timestamp).toLocaleTimeString()}]</span>
                    <div className="flex flex-col gap-1">
                       <span className="flex-1 whitespace-pre-wrap leading-relaxed">{msg.content}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub‑Bots Tab (unchanged) */}
          {activeTab === 'subagents' && (
            <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-2xl">
              <h3 className="text-xs font-black uppercase tracking-widest text-emerald-500 mb-4">Sub‑Bots</h3>
              {localSubAgentIds.length === 0 ? (
                <p className="text-zinc-500 italic">No sub‑bots assigned.</p>
              ) : (
                <ul className="space-y-2">
                  {localSubAgentIds.map(id => {
                    const sub = allAgents.find(a => a.id === id);
                    return sub ? (
                      <li key={id} className="flex items-center justify-between p-3 bg-zinc-950 rounded-xl border border-zinc-800">
                        <div>
                          <span className="font-bold text-emerald-400">{sub.name}</span>
                          <span className="text-xs text-zinc-500 ml-2">({sub.id})</span>
                        </div>
                        <span className={`text-[10px] px-2 py-1 rounded-md uppercase font-black ${sub.status === AgentStatus.RUNNING ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-500'}`}>{sub.status}</span>
                      </li>
                    ) : null;
                  })}
                </ul>
              )}
              <div className="mt-4 flex">
                <select
                  value={selectedChildId}
                  onChange={(e) => setSelectedChildId(e.target.value)}
                  className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-sm text-zinc-200"
                >
                  <option value="">Select bot to add as sub‑bot</option>
                  {allAgents
                    .filter(a => a.id !== agent.id && !localSubAgentIds.includes(a.id))
                    .map(a => (
                      <option key={a.id} value={a.id}>{a.name} ({a.id})</option>
                    ))}
                </select>
                <button
                  onClick={handleAddSubAgent}
                  className="ml-2 px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-black uppercase tracking-widest hover:bg-emerald-500 transition-colors"
                >
                  Add
                </button>
              </div>
            </div>
          )}

          {/* Skills Tab (unchanged) */}
          {activeTab === 'skills' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <h3 className="text-xs font-black uppercase tracking-widest text-emerald-500">Installed Skills</h3>
                <button
                  onClick={() => setShowSkillLibrary(true)}
                  className="px-3 py-1 bg-emerald-600 text-white rounded-lg text-xs font-black uppercase tracking-widest hover:bg-emerald-500"
                >
                  Install New Skill
                </button>
              </div>

              {installedSkills.length === 0 ? (
                <p className="text-zinc-500 italic">No skills installed.</p>
              ) : (
                <div className="space-y-4">
                  {installedSkills.map(as => {
                    const versions = skillVersions[as.skillId] || [];
                    const version = versions.find(v => v.id === as.skillVersionId);
                    return (
                      <div key={as.skillId} className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="text-lg font-bold text-emerald-400">Skill ID: {as.skillId}</h4>
                            <p className="text-xs text-zinc-500 mt-1">Version: {version?.version || as.skillVersionId}</p>
                          </div>
                          <button
                            onClick={() => handleUninstallSkill(as.skillId)}
                            className="text-red-500 hover:text-red-400"
                          >
                            <Icons.Trash />
                          </button>
                        </div>
                        {version?.configSchema && (
                          <div className="mt-4">
                            <p className="text-xs text-zinc-400 mb-2">Configuration:</p>
                            <pre className="bg-zinc-900 p-3 rounded-xl text-xs text-zinc-300 overflow-auto">
                              {JSON.stringify(as.config, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {showSkillLibrary && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                  <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 w-full max-w-4xl max-h-[80vh] overflow-y-auto">
                    <div className="flex justify-between items-center mb-6">
                      <h3 className="text-xl font-black uppercase tracking-tighter">Skill Library</h3>
                      <button onClick={() => setShowSkillLibrary(false)} className="text-zinc-500 hover:text-white">
                        <Icons.X />
                      </button>
                    </div>
                    <SkillLibrary onInstall={handleInstallSkill} showInstall={true} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-8">
          <div className="bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-xl border-l-4 border-l-emerald-500 relative overflow-hidden">
            <h3 className="text-[10px] font-black text-zinc-500 uppercase mb-6 tracking-widest">Bot Health</h3>
            <div className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between items-end text-[10px] font-black uppercase">
                  <span className="text-zinc-400">Memory Load</span>
                  <span className="text-emerald-400">{memoryLoad}%</span>
                </div>
                <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500" style={{ width: `${Math.min(100, parseInt(memoryLoad) || 0)}%` }}></div>
                </div>
              </div>
              <p className="text-xs text-zinc-400 italic bg-zinc-950 p-4 rounded-2xl border border-zinc-800">{agent.memory?.summary || "Ready for operation."}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
