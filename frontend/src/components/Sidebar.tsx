import React, { useState } from 'react';
import { Agent, AgentStatus, Hive, UserAccount } from '../types';
import { Icons } from '../constants';

interface SidebarProps {
  agents: Agent[];
  hives: Hive[];
  activeHiveId: string;
  onSelectHive: (id: string) => void;
  onCreateHive: () => void;
  onDeleteHive: (id: string) => void;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  isCreating?: boolean;
  currentView: string;
  onViewChange: (view: string) => void;
  onClose: () => void;
  currentUser?: UserAccount;
  globalConfigCategory: 'system' | 'knowledge' | 'integrations';
  globalConfigSubTab: string;
  onGlobalConfigCategoryChange: (category: 'system' | 'knowledge' | 'integrations') => void;
  onGlobalConfigSubTabChange: (subTab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  agents, 
  hives, 
  activeHiveId, 
  onSelectHive, 
  onCreateHive, 
  onDeleteHive,
  selectedId, 
  onSelect, 
  onCreate,
  onDelete,
  isCreating,
  currentView,
  onViewChange,
  onClose,
  currentUser,
  globalConfigCategory,
  globalConfigSubTab,
  onGlobalConfigCategoryChange,
  onGlobalConfigSubTabChange
}) => {
  const [showHiveList, setShowHiveList] = useState(false);
  const activeHive = hives.find(h => h.id === activeHiveId);

  const handleBackToHive = () => {
    onViewChange('command');
  };

  return (
    <aside className="w-72 h-full border-r border-zinc-800 flex flex-col bg-zinc-900/95 lg:bg-zinc-900/30 backdrop-blur-md">
      {/* Hive Switcher Section */}
      <div className="p-4 border-b border-zinc-800 bg-zinc-950/30">
        <div className="relative">
          <button 
            onClick={() => setShowHiveList(!showHiveList)}
            className="w-full flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-emerald-500/30 transition-all group"
          >
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg group-hover:bg-emerald-500/20 transition-colors">
                <Icons.Layers />
              </div>
              <div className="text-left truncate">
                <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Hive</p>
                <p className="text-xs font-bold text-zinc-100 truncate">{activeHive?.name}</p>
              </div>
            </div>
            <div className={`text-zinc-500 transition-transform duration-300 ${showHiveList ? 'rotate-180' : ''}`}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
            </div>
          </button>

          {showHiveList && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl z-50 overflow-hidden animate-in zoom-in-95 duration-200 origin-top">
              <div className="max-h-64 overflow-y-auto p-2 space-y-1">
                {hives.map(hive => (
                  <div key={hive.id} className="group relative">
                    <button
                      onClick={() => { onSelectHive(hive.id); setShowHiveList(false); }}
                      className={`w-full text-left px-4 py-3 rounded-xl transition-all flex items-center justify-between ${
                        activeHiveId === hive.id ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                      }`}
                    >
                      <div className="truncate">
                        <p className="text-xs font-bold truncate">{hive.name}</p>
                        <p className="text-[9px] opacity-50 truncate">{hive.agents.length} Bots</p>
                      </div>
                      {activeHiveId === hive.id && <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />}
                    </button>
                    {hives.length > 1 && currentUser?.role === 'GLOBAL_ADMIN' && (
                      <button 
                        onClick={(e) => { e.stopPropagation(); if (window.confirm('Delete this hive?')) onDeleteHive(hive.id); }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Icons.Trash />
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {currentUser?.role === 'GLOBAL_ADMIN' && (
                <button 
                  onClick={() => { onCreateHive(); setShowHiveList(false); }}
                  className="w-full p-4 bg-zinc-950/50 border-t border-zinc-800 text-emerald-500 hover:text-emerald-400 text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 transition-colors"
                >
                  <Icons.Plus /> New Hive
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main navigation area */}
      <div className="flex-1 overflow-y-auto p-4">
        {currentView === 'global-config' ? (
          /* Global Config Navigation */
          <div className="space-y-6">
            <button
              onClick={handleBackToHive}
              className="w-full flex items-center gap-3 px-4 py-3 text-zinc-400 hover:text-emerald-400 hover:bg-zinc-900 rounded-xl transition-all"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
              <span className="text-xs font-black uppercase tracking-widest">Back to Hive</span>
            </button>

            {/* System */}
            <div>
              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest mb-2 px-2">System</div>
              <div className="space-y-1">
                <button
                  onClick={() => { onGlobalConfigCategoryChange('system'); onGlobalConfigSubTabChange('users'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'system' && globalConfigSubTab === 'users'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Users
                </button>
                <button
                  onClick={() => { onGlobalConfigCategoryChange('system'); onGlobalConfigSubTabChange('settings'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'system' && globalConfigSubTab === 'settings'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Settings
                </button>
                <button
                  onClick={() => { onGlobalConfigCategoryChange('system'); onGlobalConfigSubTabChange('logs'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'system' && globalConfigSubTab === 'logs'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Audit Logs
                </button>
              </div>
            </div>

            {/* Knowledge */}
            <div>
              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest mb-2 px-2">Knowledge</div>
              <div className="space-y-1">
                <button
                  onClick={() => { onGlobalConfigCategoryChange('knowledge'); onGlobalConfigSubTabChange('hive-mind'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'knowledge' && globalConfigSubTab === 'hive-mind'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Hive Mind
                </button>
                <button
                  onClick={() => { onGlobalConfigCategoryChange('knowledge'); onGlobalConfigSubTabChange('system-files'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'knowledge' && globalConfigSubTab === 'system-files'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  System Files
                </button>
                <button
                  onClick={() => { onGlobalConfigCategoryChange('knowledge'); onGlobalConfigSubTabChange('skills'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'knowledge' && globalConfigSubTab === 'skills'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Skills
                </button>
                <button
                  onClick={() => { onGlobalConfigCategoryChange('knowledge'); onGlobalConfigSubTabChange('meta'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'knowledge' && globalConfigSubTab === 'meta'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Meta Bots
                </button>
              </div>
            </div>

            {/* Integrations */}
            <div>
              <div className="text-[10px] font-black text-zinc-600 uppercase tracking-widest mb-2 px-2">Integrations</div>
              <div className="space-y-1">
                <button
                  onClick={() => { onGlobalConfigCategoryChange('integrations'); onGlobalConfigSubTabChange('environment'); }}
                  className={`w-full text-left px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    globalConfigCategory === 'integrations' && globalConfigSubTab === 'environment'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300'
                  }`}
                >
                  Environment
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Hive Navigation – simplified, removed "Hive Map" and agent list */
          <>
            <button 
              onClick={() => onViewChange('command')}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                currentView === 'command' ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
              }`}
            >
              <Icons.Terminal />
              <span className="text-xs font-black uppercase tracking-widest">Command</span>
            </button>

            <button 
              onClick={() => onViewChange('cluster')}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                currentView === 'cluster' ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
              }`}
            >
              <Icons.Box />
              <span className="text-xs font-black uppercase tracking-widest">Bots</span>
            </button>

            <button 
              onClick={() => onViewChange('brain')}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                currentView === 'brain' ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
              }`}
            >
              <Icons.Layers />
              <span className="text-xs font-black uppercase tracking-widest">Brain</span>
            </button>

            <button 
              onClick={() => onViewChange('team')}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                currentView === 'team' ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
              }`}
            >
              <Icons.User />
              <span className="text-xs font-black uppercase tracking-widest">Team</span>
            </button>

            <button 
              onClick={() => onViewChange('context')}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                currentView === 'context' ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
              }`}
            >
              <Icons.File />
              <span className="text-xs font-black uppercase tracking-widest">Context</span>
            </button>

            <button 
              onClick={() => onViewChange('history')}
              className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
                currentView === 'history' ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
              }`}
            >
              <Icons.History />
              <span className="text-xs font-black uppercase tracking-widest">History</span>
            </button>
          </>
        )}
      </div>

      {/* Footer – Global Config button (only for admins) */}
      {currentUser?.role === 'GLOBAL_ADMIN' && (
        <div className="p-4 border-t border-zinc-800 bg-zinc-950/50">
          {currentView === 'global-config' ? (
            null
          ) : (
            <button 
              onClick={() => { onViewChange('global-config'); onClose(); }}
              className="w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all hover:bg-zinc-900 text-zinc-400 border border-transparent hover:border-emerald-500/30"
            >
              <Icons.Settings />
              <div className="flex-1 text-left">
                <p className="text-xs font-black uppercase tracking-widest">Global Config</p>
                <p className="text-[9px] text-zinc-500 font-bold">System Orchestration</p>
              </div>
            </button>
          )}
        </div>
      )}
    </aside>
  );
};
