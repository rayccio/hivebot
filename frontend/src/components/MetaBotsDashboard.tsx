import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';
import { LoadingSpinner } from './LoadingSpinner';
import { toast } from 'react-hot-toast';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

export const MetaBotsDashboard: React.FC = () => {
  const [selectedPeriod, setSelectedPeriod] = useState(24);
  const [metricsAgentId, setMetricsAgentId] = useState<string | null>(null);

  // Fetch meta status
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['metaStatus'],
    queryFn: () => orchestratorService.getMetaStatus(),
    refetchInterval: 60000, // refresh every minute
  });

  // Fetch test agents
  const { data: testAgents = [], isLoading: testAgentsLoading } = useQuery({
    queryKey: ['testAgents'],
    queryFn: () => orchestratorService.getTestAgents(),
  });

  // Fetch performance stats (depends on period)
  const { data: performance, isLoading: perfLoading } = useQuery({
    queryKey: ['metaPerformance', selectedPeriod],
    queryFn: () => orchestratorService.getMetaPerformance(selectedPeriod),
  });

  // Fetch logs
  const { data: logs = [], isLoading: logsLoading } = useQuery({
    queryKey: ['metaLogs'],
    queryFn: () => orchestratorService.getMetaLogs(),
  });

  // Fetch A/B tests
  const { data: abTests = [], isLoading: abTestsLoading } = useQuery({
    queryKey: ['abTests'],
    queryFn: () => orchestratorService.listABTests(),
  });

  // Fetch agent metrics when agent is selected
  const { data: selectedAgentMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['agentMetrics', metricsAgentId, selectedPeriod],
    queryFn: () => metricsAgentId ? orchestratorService.getAgentMetrics(metricsAgentId, selectedPeriod) : null,
    enabled: !!metricsAgentId,
  });

  const loading = statusLoading || testAgentsLoading || perfLoading || logsLoading || abTestsLoading;

  const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'];

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  const pieData = performance ? [
    { name: 'Test Agents', value: performance.test_agents.total_tasks, color: '#10b981' },
    { name: 'Production', value: performance.production_agents.total_tasks, color: '#3b82f6' }
  ].filter(d => d.value > 0) : [];

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-20">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-4xl font-black tracking-tighter text-zinc-100 uppercase">
            Meta <span className="text-emerald-500">Bots</span>
          </h2>
          <p className="text-zinc-500 font-medium">Self‑improvement and agent evolution monitoring.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-3 shadow-inner">
            <div className={`w-2 h-2 rounded-full ${status?.status === 'active' ? 'bg-emerald-500 animate-pulse' : 'bg-yellow-500'}`} />
            <span className="text-[10px] font-black uppercase tracking-widest text-zinc-400">
              {status?.status === 'active' ? 'Meta-Agent Active' : 'Meta-Agent Idle'}
            </span>
          </div>
          {status?.last_run && (
            <div className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-xl text-[10px] font-mono text-zinc-400">
              Last run: {new Date(status.last_run).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Period Selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">Performance period:</span>
        {[24, 48, 72, 168].map(hours => (
          <button
            key={hours}
            onClick={() => setSelectedPeriod(hours)}
            className={`px-3 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
              selectedPeriod === hours
                ? 'bg-emerald-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            {hours}h
          </button>
        ))}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Cpu /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Test Agents Created</p>
          <h3 className="text-3xl font-black text-zinc-100 tracking-tighter">{testAgents.length}</h3>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Shield /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Test Success Rate</p>
          <h3 className="text-3xl font-black text-emerald-500 tracking-tighter">
            {performance ? (performance.test_agents.success_rate * 100).toFixed(1) : '0'}%
          </h3>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Server /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Production Success</p>
          <h3 className="text-3xl font-black text-blue-500 tracking-tighter">
            {performance ? (performance.production_agents.success_rate * 100).toFixed(1) : '0'}%
          </h3>
        </div>

        <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:opacity-10 transition-opacity"><Icons.Terminal /></div>
          <p className="text-[10px] font-black text-zinc-500 uppercase tracking-widest mb-1">Improvement</p>
          <h3 className="text-3xl font-black text-purple-500 tracking-tighter">
            {performance ? ((performance.test_agents.success_rate - performance.production_agents.success_rate) * 100).toFixed(1) : '0'}%
          </h3>
        </div>
      </div>

      {/* Charts and Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Task Distribution Pie */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 shadow-2xl space-y-6 flex flex-col items-center">
          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-500 w-full">Task Distribution</h3>
          <div className="h-[250px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '12px' }}
                  itemStyle={{ fontSize: '12px', fontWeight: 'bold' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 text-[10px] font-black uppercase tracking-widest">
            {pieData.map(d => (
              <div key={d.name} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }}></div>
                <span className="text-zinc-400">{d.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Test Agents */}
        <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
          <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-500 mb-4">Recent Test Bots</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Name</th>
                  <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Parent</th>
                  <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Mutation</th>
                  <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Created</th>
                  <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Promoted</th>
                  <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {testAgents.slice(0, 5).map(agent => (
                  <tr key={agent.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="py-3 text-sm font-bold text-zinc-300">{agent.name}</td>
                    <td className="py-3 text-xs text-zinc-400">{agent.parent_id || 'None'}</td>
                    <td className="py-3 text-xs text-zinc-400">{agent.mutation || 'unknown'}</td>
                    <td className="py-3 text-xs text-zinc-400">{new Date(agent.created_at).toLocaleDateString()}</td>
                    <td className="py-3">
                      {agent.promoted ? (
                        <span className="text-emerald-400 text-xs">✓</span>
                      ) : (
                        <span className="text-zinc-600 text-xs">✗</span>
                      )}
                    </td>
                    <td className="py-3">
                      <button
                        onClick={() => setMetricsAgentId(agent.id)}
                        className="text-[10px] px-2 py-1 bg-emerald-600/10 text-emerald-400 rounded hover:bg-emerald-600/20 transition-colors"
                      >
                        Metrics
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Agent Metrics Detail */}
      {selectedAgentMetrics && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xs font-black uppercase tracking-[0.2em] text-emerald-500">
              Metrics for {selectedAgentMetrics.agent_id}
            </h3>
            <button
              onClick={() => setMetricsAgentId(null)}
              className="text-zinc-500 hover:text-white"
            >
              <Icons.X />
            </button>
          </div>
          {metricsLoading ? (
            <LoadingSpinner />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                <p className="text-[10px] text-zinc-500">Success Rate</p>
                <p className="text-2xl font-bold text-emerald-400">{(selectedAgentMetrics.success_rate * 100).toFixed(1)}%</p>
              </div>
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                <p className="text-[10px] text-zinc-500">Total Tasks</p>
                <p className="text-2xl font-bold text-zinc-200">{selectedAgentMetrics.total_tasks}</p>
              </div>
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                <p className="text-[10px] text-zinc-500">Avg Response Time</p>
                <p className="text-2xl font-bold text-zinc-200">{selectedAgentMetrics.avg_response_time_seconds}s</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* A/B Tests Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
        <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-500 mb-4">A/B Test Results</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Test Agent</th>
                <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Parent Agent</th>
                <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Mutation</th>
                <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Created</th>
                <th className="pb-3 text-[10px] font-black text-zinc-500 uppercase tracking-widest">Promoted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {abTests.map(test => (
                <tr key={test.test_agent_id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="py-3 text-sm font-bold text-zinc-300">{test.test_agent_name}</td>
                  <td className="py-3 text-xs text-zinc-400">{test.parent_agent_name}</td>
                  <td className="py-3 text-xs text-zinc-400">{test.mutation}</td>
                  <td className="py-3 text-xs text-zinc-400">{new Date(test.created_at).toLocaleDateString()}</td>
                  <td className="py-3">
                    {test.promoted ? (
                      <span className="text-emerald-400 text-xs">✓ {new Date(test.promoted_at!).toLocaleDateString()}</span>
                    ) : (
                      <span className="text-zinc-600 text-xs">✗</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Activity Logs */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl">
        <h3 className="text-xs font-black uppercase tracking-[0.2em] text-zinc-500 mb-4">Meta-Bot Activity Log</h3>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {logs.length === 0 ? (
            <p className="text-zinc-500 italic text-center py-4">No activity recorded yet.</p>
          ) : (
            logs.map((log, idx) => (
              <div key={idx} className="flex items-start gap-4 p-3 bg-zinc-950 rounded-xl border border-zinc-800">
                <div className="w-2 h-2 rounded-full bg-emerald-500 mt-2"></div>
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-emerald-400">{log.event}</span>
                    <span className="text-[9px] text-zinc-500 font-mono">{new Date(log.timestamp).toLocaleString()}</span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1">
                    Agent <span className="font-mono text-emerald-400">{log.agent_name}</span> ({log.agent_id})
                    {log.parent_agent && ` from parent ${log.parent_agent}`}
                    {log.mutation && ` (mutation: ${log.mutation})`}
                  </p>
                  {log.promoted && (
                    <p className="text-[10px] text-emerald-400 mt-1">✓ Promoted to production</p>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
