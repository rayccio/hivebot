import React, { useState } from 'react';
import { Agent, AgentStatus, Hive, UserAccount } from '../types';
import { Icons } from '../constants';

interface SidebarProps {
  agents: Agent[];                     // now active agents for the hive
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
  currentUser
}) => {
  const [showHiveList, setShowHiveList] = useState(false);
  const activeHive = hives.find(h => h.id === activeHiveId);

  return (
    <aside className="w-72 h-full border-r border-zinc-800 flex flex-col bg-zinc-900/95 lg:bg-zinc-900/30 backdrop-blur-md">
      {/* Global Config Section – only for Global Admins */}
      {currentUser?.role === 'GLOBAL_ADMIN' && (
        <div className="p-4 border-b border-zinc-800 bg-zinc-950/30">
          <div className="flex items-center justify-between mb-3 px-1">
            <span className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em]">Global</span>
          </div>
          <button 
            onClick={() => { onViewChange('global-config'); onClose(); }}
            className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
              currentView === 'global-config' ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.1)]' : 'hover:bg-zinc-900 text-zinc-400 border-transparent'
            } border`}
          >
            <Icons.Settings />
            <div className="flex-1 text-left">
              <p className="text-xs font-black uppercase tracking-widest">Global Config</p>
              <p className="text-[9px] text-zinc-500 font-bold">System Orchestration</p>
            </div>
          </button>
        </div>
      )}

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

      <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
        <span className="text-[10px] font-black text-zinc-500 uppercase tracking-[0.2em]">Active Agents</span>
        <div className="flex items-center gap-2">
          <button 
            onClick={onCreate}
            disabled={isCreating}
            className={`p-2 rounded-lg transition-all border ${
              isCreating 
                ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed' 
                : 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/10'
            }`}
            title="Spawn Agent"
          >
            {isCreating ? (
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              <Icons.Plus />
            )}
          </button>
          <button onClick={onClose} className="lg:hidden p-2 text-zinc-500 hover:text-white">
            <Icons.X />
          </button>
        </div>
      </div>
      
      <nav className="flex-1 overflow-y-auto p-4 space-y-2">
        {/* Mobile Navigation Section */}
        <div className="lg:hidden space-y-2 mb-6">
          <span className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.2em] px-4">Navigation</span>
          <div className="grid grid-cols-2 gap-2 p-2 bg-zinc-950/50 rounded-2xl border border-zinc-800/50">
            <button 
              onClick={() => onViewChange('command')}
              className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                currentView === 'command' ? 'bg-zinc-800 text-emerald-400 shadow-lg' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Command
            </button>
            <button 
              onClick={() => onViewChange('cluster')}
              className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                currentView === 'cluster' ? 'bg-zinc-800 text-emerald-400 shadow-lg' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Bots
            </button>
            <button 
              onClick={() => onViewChange('brain')}
              className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                currentView === 'brain' ? 'bg-zinc-800 text-emerald-400 shadow-lg' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Brain
            </button>
            <button 
              onClick={() => onViewChange('team')}
              className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                currentView === 'team' ? 'bg-zinc-800 text-emerald-400 shadow-lg' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Team
            </button>
            <button 
              onClick={() => onViewChange('context')}
              className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                currentView === 'context' ? 'bg-zinc-800 text-emerald-400 shadow-lg' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Context
            </button>
          </div>
          <div className="h-px bg-zinc-800/50 mx-4"></div>
        </div>

        <button 
          onClick={() => onSelect(null)}
          className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl transition-all ${
            selectedId === null ? 'bg-zinc-800 text-white shadow-xl' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/50'
          }`}
        >
          <Icons.Box />
          <span className="text-xs font-black uppercase tracking-widest">Hive Map</span>
        </button>

        <div className="my-6 border-t border-zinc-800/50 mx-4"></div>

        {agents.length === 0 && (
          <p className="text-zinc-500 text-xs italic text-center py-4">No active agents for this hive.</p>
        )}
        {agents.map(agent => (
          <div key={agent.id} className="flex items-center group">
            <button
              onClick={() => onSelect(agent.id)}
              className={`flex-1 flex items-center justify-between px-4 py-4 rounded-2xl transition-all ${
                selectedId === agent.id ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-zinc-500 hover:bg-zinc-900/50'
              }`}
            >
              <div className="flex items-center gap-4 overflow-hidden">
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                  agent.status === AgentStatus.RUNNING ? 'bg-emerald-500 animate-pulse' : 
                  agent.status === AgentStatus.ERROR ? 'bg-red-500' : 'bg-zinc-700'
                }`} />
                <div className="truncate text-left">
                  <p className="text-xs font-black truncate uppercase tracking-tighter">{agent.name}</p>
                  <p className="text-[9px] opacity-40 truncate font-mono tracking-widest">{agent.id}</p>
                </div>
              </div>
            </button>
            <button
              onClick={() => {
                if (window.confirm(`Delete agent "${agent.name}"?`)) {
                  onDelete(agent.id);
                }
              }}
              className="ml-2 p-2 text-zinc-600 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
              title="Delete Agent"
            >
              <Icons.Trash className="w-4 h-4" />
            </button>
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-zinc-800 bg-zinc-950/50 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="p-3 bg-zinc-900 rounded-xl border border-zinc-800 flex flex-col gap-1">
            <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest">Active Agents</span>
            <span className="text-xs font-mono text-emerald-400 font-bold">
              {agents.filter(a => a.status === AgentStatus.RUNNING).length} <span className="text-[8px] text-zinc-600">/ {agents.length}</span>
            </span>
          </div>
          <div className="p-3 bg-zinc-900 rounded-xl border border-zinc-800 flex flex-col gap-1">
            <span className="text-[8px] font-black text-zinc-500 uppercase tracking-widest">Hive Burn</span>
            <span className="text-xs font-mono text-zinc-200 font-bold">
              {Math.floor(agents.reduce((acc, a) => acc + a.memory.tokenCount, 0)).toLocaleString()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-[9px] font-black uppercase tracking-widest text-zinc-500 px-4 py-2 bg-zinc-900 rounded-xl border border-zinc-800">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)] animate-pulse"></div>
          Status: Synchronized
        </div>
      </div>
    </aside>
  );
};
