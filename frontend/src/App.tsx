import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Agent, AgentStatus, ReportingTarget, Message, FileEntry, AgentCreate, Hive, HiveCreate, HiveUpdate, HiveMindConfig, HiveMindAccessLevel, UserAccount, GlobalSettings, UserRole } from './types';
import { INITIAL_SOUL, INITIAL_IDENTITY, INITIAL_TOOLS, INITIAL_USER_MD, Icons } from './constants';
import { Sidebar } from './components/Sidebar';
import { AgentGrid } from './components/AgentGrid';
import { AgentDetails } from './components/AgentDetails';
import { HiveBrain } from './components/HiveBrain';
import { HiveMindDashboard } from './components/HiveMindDashboard';
import { GlobalConfig } from './components/GlobalConfig';
import { HiveTeam } from './components/HiveTeam';
import { HiveContext } from './components/HiveContext';
import { HiveCommand } from './components/HiveCommand';
import { LoginPage } from './components/LoginPage';
import { UnauthorizedPage } from './components/UnauthorizedPage';
import { ChangePasswordModal } from './components/ChangePasswordModal';
import { LoadingSpinner } from './components/LoadingSpinner';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ProviderProvider, useProviders } from './contexts/ProviderContext';
import { BridgeProvider } from './contexts/BridgeContext';
import { orchestratorService } from './services/orchestratorService';
import { wsService } from './services/websocketService';
import { toast } from 'react-hot-toast';
import { AlertModal } from './components/Modal';
import { ExecutionHistory } from './components/ExecutionHistory';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 60 * 5,
    },
  },
});

const AppContent: React.FC = () => {
  const { user, loading: authLoading, gatewayEnabled, logout, changePassword, refreshGatewayState } = useAuth();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showDefaultPasswordToast, setShowDefaultPasswordToast] = useState(false);
  const [pendingUser, setPendingUser] = useState<any>(null);
  
  const [hives, setHives] = useState<Hive[]>([]);
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [activeHiveId, setActiveHiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [creatingBotId, setCreatingBotId] = useState<string | null>(null);
  
  const [activeAgents, setActiveAgents] = useState<Agent[]>([]);
  
  const [globalSettings, setGlobalSettings] = useState<GlobalSettings>({
    loginEnabled: false,
    sessionTimeout: 30,
    systemName: 'HiveBot Orchestrator',
    maintenanceMode: false,
    defaultAgentUid: '10001',
    rateLimitEnabled: true,
    rateLimitRequests: 100,
    rateLimitPeriodSeconds: 60
  });

  const [view, setView] = useState<'command' | 'cluster' | 'agent' | 'context' | 'brain' | 'team' | 'global-config' | 'history'>('command');
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const [globalConfigCategory, setGlobalConfigCategory] = useState<'system' | 'knowledge' | 'integrations'>('system');
  const [globalConfigSubTab, setGlobalConfigSubTab] = useState<string>('users');

  const { getPrimaryModel, refreshProviders } = useProviders();
  const [showNoPrimaryModal, setShowNoPrimaryModal] = useState(false);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (user && !user.password_changed && gatewayEnabled && !showDefaultPasswordToast) {
      toast(
        <div>
          <strong>Default Admin Password</strong>
          <p className="text-sm mt-1">Check the backend logs for the generated password.</p>
          <p className="text-xs text-zinc-400 mt-2">You must change your password before enabling the login gateway.</p>
        </div>,
        {
          duration: 10000,
          position: 'top-center',
          icon: '🔐'
        }
      );
      setShowDefaultPasswordToast(true);
    }
  }, [user, gatewayEnabled, showDefaultPasswordToast]);

  useEffect(() => {
    if (user && !user.password_changed && gatewayEnabled) {
      setShowChangePassword(true);
    }
  }, [user, gatewayEnabled]);

  useEffect(() => {
    const loadInitialData = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        setLoadError(null);
        
        const promises: Promise<any>[] = [
          orchestratorService.getGlobalSettings().catch(err => {
            console.warn('Could not fetch global settings, using defaults', err);
            return null;
          }),
          user.role === 'GLOBAL_ADMIN'
            ? orchestratorService.listUsers().catch(err => {
                console.warn('Could not fetch users', err);
                return [];
              })
            : Promise.resolve([]),
          orchestratorService.listHives().catch(err => {
            console.warn('Could not fetch hives, will create default', err);
            return [];
          })
        ];

        const [settingsResult, usersResult, hivesResult] = await Promise.all(promises);

        if (settingsResult) setGlobalSettings(settingsResult);
        if (usersResult) setUsers(usersResult);

        let hivesData = hivesResult as Hive[];
        
        if (hivesData.length === 0) {
          try {
            const defaultHive = await orchestratorService.createHive({
              name: 'Main Hive',
              description: 'Primary cluster for bot orchestration',
              globalUserMd: INITIAL_USER_MD,
            });
            hivesData = [defaultHive];
          } catch (err) {
            console.error('Failed to create default hive', err);
            setLoadError('Could not initialize hive. Please check backend connection.');
            setLoading(false);
            return;
          }
        }
        
        setHives(hivesData);
        
        const savedActive = localStorage.getItem('hivebot_active_hive');
        if (savedActive && hivesData.some(h => h.id === savedActive)) {
          setActiveHiveId(savedActive);
        } else {
          setActiveHiveId(hivesData[0].id);
          setView('command');
        }

        refreshProviders().catch(err => 
          console.warn('Could not load providers', err)
        );

      } catch (err) {
        console.error('Failed to load initial data', err);
        setLoadError('Failed to connect to backend. Please check server status.');
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, [user, refreshProviders]);

  const fetchActiveAgents = useCallback(async (hiveId: string) => {
    try {
      const agents = await orchestratorService.getHiveActiveAgents(hiveId);
      setActiveAgents(agents);
    } catch (err) {
      console.warn('Could not fetch active agents', err);
    }
  }, []);

  useEffect(() => {
    if (activeHiveId) {
      fetchActiveAgents(activeHiveId);
      intervalRef.current = setInterval(() => {
        fetchActiveAgents(activeHiveId);
      }, 10000);
    } else {
      setActiveAgents([]);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [activeHiveId, fetchActiveAgents]);

  useEffect(() => {
    if (activeHiveId) {
      localStorage.setItem('hivebot_active_hive', activeHiveId);
    }
  }, [activeHiveId]);

  useEffect(() => {
    if (user) {
      const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      wsService.connect(apiBaseUrl);

      const handler = (data: any) => {
        if (data.agent_id && data.response && activeHiveId) {
          const msg: Message = {
            id: Math.random().toString(36).substr(2, 9),
            from: data.agent_id,
            to: 'system',
            content: data.response,
            timestamp: data.timestamp || new Date().toISOString(),
            type: 'chat',
          };
          
          setHives(prev => prev.map(h => 
            h.id === activeHiveId 
              ? { 
                  ...h, 
                  messages: [msg, ...h.messages].slice(0, 100),
                  agents: h.agents.map(a => 
                    a.id === data.agent_id ? { ...a, status: AgentStatus.IDLE } : a
                  )
                }
              : h
          ));
        }
      };

      wsService.addHandler(handler);
      return () => {
        wsService.removeHandler(handler);
        wsService.disconnect();
      };
    }
  }, [user, activeHiveId]);

  const activeHive = useMemo(() => 
    hives.find(h => h.id === activeHiveId) || hives[0]
  , [hives, activeHiveId]);

  const hiveAgents = activeHive?.agents || [];
  const globalUserMd = activeHive?.globalUserMd || INITIAL_USER_MD;
  const messages = activeHive?.messages || [];
  const globalFiles = activeHive?.globalFiles || [];

  const selectedAgent = useMemo(() => 
    (activeAgents.find(a => a.id === selectedAgentId) || hiveAgents.find(a => a.id === selectedAgentId)) || null
  , [activeAgents, hiveAgents, selectedAgentId]);

  const updateHive = async (hiveId: string, updates: HiveUpdate) => {
    setHives(prev =>
      prev.map(h => (h.id === hiveId ? { ...h, ...updates } : h))
    );
    try {
      const updated = await orchestratorService.updateHive(hiveId, updates);
      setHives(prev =>
        prev.map(h => (h.id === hiveId ? updated : h))
      );
      return updated;
    } catch (err) {
      console.error('Failed to update hive', err);
      const fresh = await orchestratorService.getHive(hiveId);
      setHives(prev => prev.map(h => (h.id === hiveId ? fresh : h)));
      throw err;
    }
  };

  const handleUpdateAgent = async (updated: Agent) => {
    if (!activeHiveId) return;
    try {
      const result = await orchestratorService.updateHiveAgent(activeHiveId, updated.id, updated);
      setHives(prev => prev.map(h => 
        h.id === activeHiveId 
          ? { ...h, agents: h.agents.map(a => a.id === updated.id ? result : a) }
          : h
      ));
      setActiveAgents(prev => prev.map(a => a.id === updated.id ? result : a));
    } catch (err) {
      console.error('Update failed', err);
    }
  };

  const handleCreateAgent = async () => {
    if (!activeHiveId) return;
    const primaryModel = getPrimaryModel();
    if (!primaryModel) {
      setShowNoPrimaryModal(true);
      return;
    }

    const tempId = `temp-${Date.now()}`;
    setCreatingBotId(tempId);
    setView('agent');
    setSelectedAgentId(tempId);

    try {
      const agentCreate: AgentCreate = {
        name: 'New HiveBot',
        role: 'generic',
        soulMd: INITIAL_SOUL,
        identityMd: INITIAL_IDENTITY,
        toolsMd: INITIAL_TOOLS,
        reasoning: {
          model: `${primaryModel.provider}:${primaryModel.modelId}`,
          temperature: 0.7,
          topP: 1.0,
          maxTokens: 150,
          use_global_default: true,
          use_custom_max_tokens: false,
        },
        reportingTarget: ReportingTarget.PARENT,
        parentId: hiveAgents.length > 0 ? hiveAgents[0].id : undefined,
        userUid: globalSettings.defaultAgentUid,
        channels: [],
      };

      const created = await orchestratorService.createAgent(agentCreate);
      const added = await orchestratorService.addAgentToHive(activeHiveId, created);
      
      setHives(prev => prev.map(h => 
        h.id === activeHiveId 
          ? { ...h, agents: [...h.agents, added] }
          : h
      ));
      
      setSelectedAgentId(added.id);
      
      addLog(added.id, 'Bot spawned successfully. Initializing...', 'internal');
      
    } catch (err) {
      console.error('Create failed', err);
      toast.error('Failed to create bot. Check console for details.');
      setSelectedAgentId(null);
      setView('cluster');
    } finally {
      setCreatingBotId(null);
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!activeHiveId) return;
    try {
      await orchestratorService.removeAgentFromHive(activeHiveId, agentId);
      setHives(prev => prev.map(h => 
        h.id === activeHiveId 
          ? { ...h, agents: h.agents.filter(a => a.id !== agentId) }
          : h
      ));
      setActiveAgents(prev => prev.filter(a => a.id !== agentId));
      if (selectedAgentId === agentId) {
        setSelectedAgentId(null);
        setView('cluster');
      }
    } catch (err) {
      console.error('Delete failed', err);
    }
  };

  const handleCreateHive = async () => {
    try {
      const newHive = await orchestratorService.createHive({
        name: 'New Hive',
        description: 'Autonomous bot orchestration hive',
        globalUserMd: INITIAL_USER_MD,
      });
      setHives(prev => [...prev, newHive]);
      setActiveHiveId(newHive.id);
      setView('command');
      setSelectedAgentId(null);
      setIsSidebarOpen(false);
    } catch (err) {
      console.error('Failed to create hive', err);
    }
  };

  const handleDeleteHive = async (id: string) => {
    if (hives.length <= 1) {
      alert('Cannot delete the last hive');
      return;
    }
    try {
      await orchestratorService.deleteHive(id);
      setHives(prev => {
        const filtered = prev.filter(h => h.id !== id);
        if (activeHiveId === id && filtered.length > 0) {
          setActiveHiveId(filtered[0].id);
        }
        return filtered;
      });
    } catch (err) {
      console.error('Failed to delete hive', err);
    }
  };

  const runAgent = async (agentId: string) => {
    if (!activeHiveId) return;
    
    try {
      setHives(prev => prev.map(h => 
        h.id === activeHiveId 
          ? { 
              ...h, 
              agents: h.agents.map(a => 
                a.id === agentId ? { ...a, status: AgentStatus.RUNNING } : a
              )
            }
          : h
      ));
      setActiveAgents(prev => prev.map(a => a.id === agentId ? { ...a, status: AgentStatus.RUNNING } : a));
      
      addLog(agentId, `Initiating Hive Cycle...`, 'internal');
      
      await orchestratorService.executeAgent(agentId);
    } catch (err: any) {
      addLog(agentId, `HIVE_FAULT: ${err.message}`, 'error');
      setHives(prev => prev.map(h => 
        h.id === activeHiveId 
          ? { 
              ...h, 
              agents: h.agents.map(a => 
                a.id === agentId ? { ...a, status: AgentStatus.ERROR } : a
              )
            }
          : h
      ));
      setActiveAgents(prev => prev.map(a => a.id === agentId ? { ...a, status: AgentStatus.ERROR } : a));
    }
  };

  const addLog = useCallback((agentId: string, content: string, type: Message['type'] = 'log', channelId?: string) => {
    if (!activeHiveId) return;
    const newMessage: Message = {
      id: Math.random().toString(36).substr(2, 9),
      from: agentId,
      to: 'system',
      content,
      timestamp: new Date().toISOString(),
      type,
      channelId
    };
    
    setHives(prev => prev.map(h => 
      h.id === activeHiveId 
        ? { 
            ...h, 
            messages: [newMessage, ...h.messages].slice(0, 100)
          }
        : h
    ));
    
    orchestratorService.addMessageToHive(activeHiveId, newMessage).catch(console.error);
  }, [activeHiveId]);

  const handleSelectHive = (id: string) => {
    setActiveHiveId(id);
    setView('command');
    setSelectedAgentId(null);
    setIsSidebarOpen(false);
  };

  const handleSelectAgent = (id: string | null) => {
    setSelectedAgentId(id);
    if (id) {
      setView('agent');
    } else {
      setView('cluster');
    }
    setIsSidebarOpen(false);
  };

  const handlePasswordChangeSuccess = () => {
    setShowChangePassword(false);
    if (user) {
      user.password_changed = true;
    }
    if (pendingUser) {
      handleCreateUser(pendingUser).finally(() => setPendingUser(null));
    }
    const pendingAction = (window as any).__pendingAction;
    if (pendingAction) {
      pendingAction();
      (window as any).__pendingAction = null;
    }
  };

  // ========== USER MANAGEMENT ==========
  const loadUsers = async () => {
    try {
      const usersData = await orchestratorService.listUsers();
      setUsers(usersData);
    } catch (err) {
      console.error('Failed to load users', err);
      toast.error('Failed to load users');
    }
  };

  const handleCreateUser = async (userData: {
    username: string;
    password: string;
    role: UserRole;
    assignedHiveIds: string[];
  }) => {
    if (!gatewayEnabled && user && !user.password_changed) {
      setPendingUser(userData);
      setShowChangePassword(true);
      return;
    }

    try {
      const created = await orchestratorService.createUser(userData);
      setUsers(prev => [...prev, created]);
      
      if (!gatewayEnabled) {
        await handleToggleLoginGateway(true);
      }
      
      toast.success(`User ${created.username} created successfully`);
      return created;
    } catch (err: any) {
      console.error('Failed to create user', err);
      toast.error(err.message || 'Failed to create user');
      throw err;
    }
  };

  const handleUpdateUser = async (userId: string, updates: {
    username?: string;
    password?: string;
    role?: UserRole;
    assignedHiveIds?: string[];
  }) => {
    try {
      const updated = await orchestratorService.updateUser(userId, updates);
      setUsers(prev => prev.map(u => u.id === userId ? updated : u));
      toast.success('User updated successfully');
      return updated;
    } catch (err: any) {
      console.error('Failed to update user', err);
      toast.error(err.message || 'Failed to update user');
      throw err;
    }
  };

  const handleDeleteUser = async (userId: string) => {
    try {
      await orchestratorService.deleteUser(userId);
      setUsers(prev => prev.filter(u => u.id !== userId));
      toast.success('User deleted successfully');
    } catch (err: any) {
      console.error('Failed to delete user', err);
      toast.error(err.message || 'Failed to delete user');
      throw err;
    }
  };

  const handleToggleLoginGateway = async (enabled: boolean) => {
    try {
      const newSettings = { ...globalSettings, loginEnabled: enabled };
      await orchestratorService.setGlobalSettings(newSettings);
      setGlobalSettings(newSettings);
      await refreshGatewayState();
      toast.success(`Login gateway ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err: any) {
      console.error('Failed to toggle login gateway', err);
      toast.error(err.message || 'Failed to update settings');
      throw err;
    }
  };

  const refreshGlobalSettings = async () => {
    try {
      const settings = await orchestratorService.getGlobalSettings();
      setGlobalSettings(settings);
    } catch (err) {
      console.error('Failed to refresh global settings', err);
    }
  };

  if (authLoading || (loading && user)) {
    return (
      <div className="flex items-center justify-center h-screen bg-zinc-950">
        <div className="text-center">
          <div className="text-emerald-500 text-2xl font-black mb-4 animate-pulse">HiveBot</div>
          <LoadingSpinner size="lg" />
          <div className="text-zinc-500 mt-4">Loading hive intelligence...</div>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-zinc-950 overflow-hidden select-none text-zinc-100 font-sans relative">
        <div className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity lg:hidden ${isSidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} onClick={() => setIsSidebarOpen(false)} />
        
        <div className={`fixed lg:relative inset-y-0 left-0 z-50 transform transition-transform duration-300 lg:translate-x-0 ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
          <Sidebar 
            agents={activeAgents}
            hives={hives}
            activeHiveId={activeHiveId || ''}
            onSelectHive={handleSelectHive}
            onCreateHive={handleCreateHive}
            onDeleteHive={handleDeleteHive}
            selectedId={selectedAgentId} 
            onSelect={handleSelectAgent}
            onCreate={handleCreateAgent}
            onDelete={handleDeleteAgent}
            isCreating={creatingBotId !== null}
            currentView={view}
            onViewChange={(v) => { setView(v); setIsSidebarOpen(false); }}
            onClose={() => setIsSidebarOpen(false)}
            currentUser={user}
            globalConfigCategory={globalConfigCategory}
            globalConfigSubTab={globalConfigSubTab}
            onGlobalConfigCategoryChange={setGlobalConfigCategory}
            onGlobalConfigSubTabChange={setGlobalConfigSubTab}
          />
        </div>

        <main className="flex-1 flex flex-col overflow-hidden relative">
          {/* Header - only show when not in global-config */}
          {view !== 'global-config' && ['command', 'cluster', 'agent', 'context', 'brain', 'team', 'history'].includes(view) && (
            <header className="h-16 border-b border-zinc-800 flex items-center justify-between px-4 md:px-8 bg-zinc-950/90 backdrop-blur-md sticky top-0 z-20">
              <div className="flex items-center gap-3 md:gap-4">
                <button onClick={() => setIsSidebarOpen(true)} className="lg:hidden p-2 text-zinc-400 hover:text-white transition-colors">
                  <Icons.Menu />
                </button>
                <div className="p-1.5 md:p-2 bg-emerald-500/10 text-emerald-500 rounded-lg shadow-inner"><Icons.Shield /></div>
                <h1 className="font-black tracking-tighter text-lg md:text-2xl uppercase">Hive<span className="text-emerald-500">Bot</span></h1>
              </div>
              
              <div className="flex items-center gap-2 md:gap-6">
                <div className="hidden lg:flex bg-zinc-900 p-1 rounded-2xl border border-zinc-800 shadow-inner">
                  <button onClick={() => setView('command')} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'command' ? 'bg-zinc-800 text-emerald-400 shadow-xl' : 'text-zinc-500 hover:text-zinc-300'}`}>Command</button>
                  <button onClick={() => setView('cluster')} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'cluster' ? 'bg-zinc-800 text-emerald-400 shadow-xl' : 'text-zinc-500 hover:text-zinc-300'}`}>Bots</button>
                  <button onClick={() => setView('brain')} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'brain' ? 'bg-zinc-800 text-emerald-400 shadow-xl' : 'text-zinc-500 hover:text-zinc-300'}`}>Brain</button>
                  <button onClick={() => setView('team')} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'team' ? 'bg-zinc-800 text-emerald-400 shadow-xl' : 'text-zinc-500 hover:text-zinc-300'}`}>Team</button>
                  <button onClick={() => setView('context')} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'context' ? 'bg-zinc-800 text-emerald-400 shadow-xl' : 'text-zinc-500 hover:text-zinc-300'}`}>Context</button>
                  <button onClick={() => setView('history')} className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'history' ? 'bg-zinc-800 text-emerald-400 shadow-xl' : 'text-zinc-500 hover:text-zinc-300'}`}>History</button>
                </div>
                
                <div className="w-px h-6 bg-zinc-800 hidden lg:block"></div>
                
                {gatewayEnabled && (
                  <button 
                    onClick={logout}
                    className="flex items-center gap-2 px-2 md:px-3 py-1.5 text-zinc-500 hover:text-red-400 transition-all bg-zinc-900/50 rounded-lg md:rounded-xl border border-zinc-800 hover:border-red-500/20 group"
                    title="Terminate Session"
                  >
                    <span className="text-[9px] font-black uppercase tracking-widest hidden md:inline">Terminate</span>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="group-hover:translate-x-0.5 transition-transform"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                  </button>
                )}
              </div>
            </header>
          )}

          {/* Global Config header */}
          {view === 'global-config' && (
            <header className="h-16 border-b border-zinc-800 flex items-center justify-between px-4 md:px-8 bg-zinc-950/90 backdrop-blur-md sticky top-0 z-20">
              <div className="flex items-center gap-3 md:gap-4">
                <button onClick={() => setIsSidebarOpen(true)} className="lg:hidden p-2 text-zinc-400 hover:text-white transition-colors">
                  <Icons.Menu />
                </button>
                <div className="p-1.5 md:p-2 bg-emerald-500/10 text-emerald-500 rounded-lg shadow-inner"><Icons.Shield /></div>
                <h1 className="font-black tracking-tighter text-lg md:text-2xl uppercase">Hive<span className="text-emerald-500">Bot</span></h1>
              </div>
              
              <div className="flex items-center gap-2 md:gap-6">
                <div className="w-px h-6 bg-zinc-800 hidden lg:block"></div>
                
                {gatewayEnabled && (
                  <button 
                    onClick={logout}
                    className="flex items-center gap-2 px-2 md:px-3 py-1.5 text-zinc-500 hover:text-red-400 transition-all bg-zinc-900/50 rounded-lg md:rounded-xl border border-zinc-800 hover:border-red-500/20 group"
                    title="Terminate Session"
                  >
                    <span className="text-[9px] font-black uppercase tracking-widest hidden md:inline">Terminate</span>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="group-hover:translate-x-0.5 transition-transform"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                  </button>
                )}
              </div>
            </header>
          )}

          <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-gradient-to-b from-zinc-950 to-zinc-900/40">
            {view === 'global-config' && user?.role === 'GLOBAL_ADMIN' && (
              <GlobalConfig 
                hives={hives} 
                users={users}
                settings={globalSettings} 
                onUpdateUsers={setUsers}
                onUpdateSettings={setGlobalSettings}
                onCreateUser={handleCreateUser}
                onUpdateUser={handleUpdateUser}
                onDeleteUser={handleDeleteUser}
                onToggleLoginGateway={handleToggleLoginGateway}
                gatewayEnabled={gatewayEnabled}
                currentUser={user}
                onRequirePasswordChange={(action) => {
                  setShowChangePassword(true);
                  (window as any).__pendingAction = action;
                }}
                onLoadUsers={loadUsers}
                onRefreshSettings={refreshGlobalSettings}
                category={globalConfigCategory}
                subTab={globalConfigSubTab}
                onCategoryChange={setGlobalConfigCategory}
                onSubTabChange={setGlobalConfigSubTab}
              />
            )}

            {view === 'command' && activeHive && (
              <HiveCommand 
                hive={activeHive} 
                agents={hiveAgents}
                onRunAgent={runAgent}
              />
            )}

            {view === 'brain' && activeHive && (
              <HiveBrain 
                hive={activeHive} 
                allHives={hives}
                onUpdate={(config) => updateHive(activeHive.id, { hiveMindConfig: config })}
              />
            )}

            {view === 'team' && activeHive && (
              <HiveTeam 
                hive={activeHive}
                allUsers={users}
                onUpdateUsers={setUsers}
                currentUser={user}
              />
            )}

            {view === 'context' && activeHive && (
              <HiveContext
                hive={activeHive}
                onUpdateHive={updateHive}
              />
            )}

            {view === 'history' && activeHive && (
              <ExecutionHistory hive={activeHive} />
            )}

            {view === 'agent' && (
              selectedAgentId === creatingBotId ? (
                <div className="flex items-center justify-center min-h-[400px]">
                  <div className="text-center">
                    <LoadingSpinner size="lg" />
                    <p className="text-zinc-400 mt-4">Spawning new bot...</p>
                  </div>
                </div>
              ) : (
                selectedAgent && (
                  <AgentDetails 
                    agent={selectedAgent} 
                    onUpdate={handleUpdateAgent} 
                    onRun={() => runAgent(selectedAgent.id)}
                    onDelete={handleDeleteAgent}
                    messages={messages.filter(m => m.from === selectedAgent.id)}
                    allAgents={activeAgents}
                    globalFiles={globalFiles}
                  />
                )
              )
            )}

            {view === 'cluster' && (
              <div className="space-y-12">
                <div className="space-y-2">
                  <h2 className="text-4xl font-black tracking-tighter">Hive Overview</h2>
                  <p className="text-zinc-500 text-lg">Active mesh topology and bot status.</p>
                </div>
                <AgentGrid 
                  agents={activeAgents} 
                  onSelect={(id) => { 
                    setSelectedAgentId(id); 
                    setView('agent'); 
                    setIsSidebarOpen(false); 
                  }} 
                />
              </div>
            )}
          </div>
        </main>
      </div>

      {showChangePassword && (
        <ChangePasswordModal
          onClose={() => setShowChangePassword(false)}
          onSuccess={handlePasswordChangeSuccess}
        />
      )}

      <AlertModal
        isOpen={showNoPrimaryModal}
        onClose={() => setShowNoPrimaryModal(false)}
        title="Primary AI Not Configured"
        message="A primary AI model is required to create an agent. Please go to Global Config > Integrations > Environment and set up a provider with a primary model."
        confirmText="OK"
      />
    </ErrorBoundary>
  );
};

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ProviderProvider>
            <BridgeProvider>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/unauthorized" element={<UnauthorizedPage />} />
                <Route
                  path="/*"
                  element={
                    <ProtectedRoute>
                      <AppContent />
                    </ProtectedRoute>
                  }
                />
              </Routes>
            </BridgeProvider>
          </ProviderProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

export default App;
