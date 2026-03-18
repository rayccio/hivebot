// frontend/src/components/HiveCommand.tsx
import React, { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Hive, Agent, HiveTask } from '../types';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';
import { LoadingSpinner } from './LoadingSpinner';
import { toast } from 'react-hot-toast';

interface HiveCommandProps {
  hive: Hive;
  agents: Agent[];
  onRunAgent: (agentId: string) => void;
}

export const HiveCommand: React.FC<HiveCommandProps> = ({ hive, agents, onRunAgent }) => {
  const [goalInput, setGoalInput] = useState('');
  const [executing, setExecuting] = useState(false);
  const [currentGoalId, setCurrentGoalId] = useState<string | null>(null);

  // Fetch recent goals for this hive
  const { data: goals = [], isLoading: goalsLoading } = useQuery({
    queryKey: ['goals', hive.id],
    queryFn: () => orchestratorService.listGoals(hive.id),
    refetchInterval: 10000,
  });

  // Determine the active goal (planning or executing)
  const activeGoal = useMemo(() => {
    return goals.find(g => g.status === 'planning' || g.status === 'executing');
  }, [goals]);

  // If there's an active goal, set its id for task polling
  useEffect(() => {
    if (activeGoal) {
      setCurrentGoalId(activeGoal.id);
    } else {
      setCurrentGoalId(null);
    }
  }, [activeGoal]);

  // Fetch tasks for the current goal
  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ['tasks', hive.id, currentGoalId],
    queryFn: () => currentGoalId ? orchestratorService.listTasksForGoal(hive.id, currentGoalId) : [],
    enabled: !!currentGoalId,
    refetchInterval: 2000,
  });

  // Fetch artifacts for the current goal
  const { data: artifacts = [], isLoading: artifactsLoading } = useQuery({
    queryKey: ['artifacts', currentGoalId],
    queryFn: () => currentGoalId ? orchestratorService.listArtifacts(hive.id, currentGoalId) : [],
    enabled: !!currentGoalId,
    refetchInterval: 5000,
  });

  const handleExecute = async () => {
    if (!goalInput.trim()) return;
    setExecuting(true);
    try {
      const result = await orchestratorService.createGoal(hive.id, {
        description: goalInput,
        constraints: {},
        success_criteria: [],
      });
      setCurrentGoalId(result.goal.id);
      toast.success('Goal created – tasks are being assigned.');
      setGoalInput('');
    } catch (err) {
      console.error('Failed to create goal', err);
      toast.error('Failed to create goal. Check console.');
    } finally {
      setExecuting(false);
    }
  };

  const handleCancelGoal = async () => {
    if (!activeGoal) return;
    if (!confirm('Cancel current goal? This will stop all associated tasks.')) return;
    // TODO: implement goal cancellation API
    toast('Goal cancellation not yet implemented');
  };

  // Stats
  const stats = useMemo(() => {
    const totalTokens = agents.reduce((acc, a) => acc + a.memory.tokenCount, 0);
    const activeNodes = agents.filter(a => a.status === 'RUNNING').length;
    const totalNodes = agents.length;
    const ramUsage = agents.reduce((acc, a) => acc + (a.status === 'RUNNING' ? 128 : 32), 0);
    const diskUsage = agents.reduce((acc, a) => acc + 45 + (a.localFiles.length * 2), 0);
    return {
      totalTokens,
      activeNodes,
      totalNodes,
      ramUsage,
      diskUsage,
      ramLimit: totalNodes * 256,
      diskLimit: totalNodes * 500
    };
  }, [agents]);

  const pendingTasks = tasks.filter(t => t.status === 'pending').length;
  const assignedTasks = tasks.filter(t => t.status === 'assigned').length;
  const completedTasks = tasks.filter(t => t.status === 'completed').length;

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-4xl font-black tracking-tighter text-zinc-100 uppercase">
            Hive <span className="text-emerald-500">Command</span>
          </h2>
          <p className="text-zinc-500 font-medium">Issue orders and monitor execution.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-3 shadow-inner">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            <span className="text-[10px] font-black uppercase tracking-widest text-zinc-400">
              {activeGoal ? 'Active Goal' : 'Idle'}
            </span>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Cpu /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Compute Load</p>
          <h3 className="text-3xl font-black text-zinc-100 tracking-tighter">{stats.activeNodes} <span className="text-sm text-zinc-500">/ {stats.totalNodes} Bots</span></h3>
          <div className="mt-4 h-1 w-full bg-zinc-800 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 transition-all duration-1000" style={{ width: `${(stats.activeNodes / stats.totalNodes) * 100}%` }}></div>
          </div>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Shield /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Task Progress</p>
          <h3 className="text-3xl font-black text-emerald-500 tracking-tighter">{completedTasks} <span className="text-sm text-zinc-500">/ {tasks.length}</span></h3>
          <p className="text-[10px] text-zinc-500 mt-2 font-mono">{pendingTasks} pending, {assignedTasks} assigned</p>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Server /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Disk Allocation</p>
          <h3 className="text-3xl font-black text-zinc-100 tracking-tighter">{stats.diskUsage} <span className="text-sm text-zinc-500">MB</span></h3>
          <p className="text-[10px] text-zinc-500 mt-2 font-mono">Limit: {stats.diskLimit} MB</p>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Terminal /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Token Consumption</p>
          <h3 className="text-3xl font-black text-emerald-500 tracking-tighter">{Math.floor(stats.totalTokens).toLocaleString()}</h3>
          <p className="text-[10px] text-zinc-500 mt-2 font-mono">Hive Lifetime Burn</p>
        </div>
      </div>

      {/* Goal Input Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
        <h3 className="text-xs font-black uppercase tracking-[0.2em] text-emerald-500 mb-4">Issue New Order</h3>
        <div className="flex flex-col md:flex-row gap-4">
          <textarea
            value={goalInput}
            onChange={(e) => setGoalInput(e.target.value)}
            placeholder="Describe your objective... e.g., 'Build a REST API for a todo app with JWT auth'"
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:border-emerald-500 outline-none resize-none h-24"
          />
          <button
            onClick={handleExecute}
            disabled={executing || !goalInput.trim()}
            className="px-8 py-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-black uppercase tracking-widest transition-all shadow-2xl flex items-center gap-3 self-end"
          >
            {executing ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Executing...</span>
              </>
            ) : (
              <>
                <Icons.Terminal />
                <span>Execute</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Active Goal Section */}
      {activeGoal && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-black uppercase tracking-[0.2em] text-emerald-500">Active Goal</h3>
            <button
              onClick={handleCancelGoal}
              className="px-3 py-1 bg-red-600/20 text-red-400 rounded-lg text-[10px] font-black uppercase tracking-widest hover:bg-red-600/30 transition-colors"
            >
              Cancel
            </button>
          </div>
          <p className="text-sm text-zinc-300 mb-4">{activeGoal.description}</p>

          {/* Task Graph */}
          {tasksLoading ? (
            <div className="flex justify-center py-8">
              <LoadingSpinner />
            </div>
          ) : tasks.length === 0 ? (
            <p className="text-zinc-500 italic text-center py-4">No tasks yet. Planning in progress...</p>
          ) : (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {tasks.map(task => (
                <div key={task.id} className="flex items-center justify-between p-4 bg-zinc-950 rounded-xl border border-zinc-800">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${
                        task.status === 'completed' ? 'bg-emerald-500' :
                        task.status === 'assigned' ? 'bg-blue-500' :
                        task.status === 'running' ? 'bg-yellow-500 animate-pulse' :
                        'bg-zinc-600'
                      }`} />
                      <span className="text-sm font-bold text-zinc-300">{task.description}</span>
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">
                      ID: {task.id} | Type: {task.agent_type} | Retries: {task.retries}
                      {task.assigned_agent_id && (
                        <span className="ml-2 text-emerald-400">
                          Assigned to {agents.find(a => a.id === task.assigned_agent_id)?.name || task.assigned_agent_id}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Recent Artifacts */}
          {artifacts.length > 0 && (
            <div className="mt-6 pt-4 border-t border-zinc-800">
              <h4 className="text-xs font-black uppercase tracking-widest text-zinc-500 mb-3">Recent Artifacts</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {artifacts.slice(0, 4).map(art => (
                  <a
                    key={art.id}
                    href={orchestratorService.getArtifactDownloadUrl(hive.id, activeGoal.id, art.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 p-2 bg-zinc-950 rounded-lg border border-zinc-800 hover:border-emerald-500/30 transition-colors"
                  >
                    <Icons.File className="text-emerald-500 w-4 h-4" />
                    <span className="text-xs text-zinc-300 truncate">{art.file_path}</span>
                    <span className="text-[9px] text-zinc-500 ml-auto">v{art.version}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
