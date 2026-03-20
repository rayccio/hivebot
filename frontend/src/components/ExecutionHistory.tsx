import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Hive } from '../types';
import { orchestratorService } from '../services/orchestratorService';
import { LoadingSpinner } from './LoadingSpinner';
import { Icons } from '../constants';
import { toast } from 'react-hot-toast';
import { ConfirmationModal } from './Modal';

interface ExecutionHistoryProps {
  hive: Hive;
}

export const ExecutionHistory: React.FC<ExecutionHistoryProps> = ({ hive }) => {
  const queryClient = useQueryClient();
  const [cancelGoalId, setCancelGoalId] = useState<string | null>(null);
  const [showCancelModal, setShowCancelModal] = useState(false);

  const { data: goals = [], isLoading, error } = useQuery({
    queryKey: ['goals', hive.id],
    queryFn: () => orchestratorService.listGoals(hive.id),
    refetchInterval: 5000,
  });

  const cancelMutation = useMutation({
    mutationFn: (goalId: string) => orchestratorService.cancelGoal(hive.id, goalId),
    onSuccess: () => {
      toast.success('Goal cancelled');
      queryClient.invalidateQueries({ queryKey: ['goals', hive.id] });
      setShowCancelModal(false);
      setCancelGoalId(null);
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to cancel goal');
      setShowCancelModal(false);
    },
  });

  const handleCancelClick = (goalId: string) => {
    setCancelGoalId(goalId);
    setShowCancelModal(true);
  };

  const confirmCancel = () => {
    if (cancelGoalId) {
      cancelMutation.mutate(cancelGoalId);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      created: 'bg-zinc-600',
      planning: 'bg-blue-600',
      executing: 'bg-yellow-600 animate-pulse',
      completed: 'bg-emerald-600',
      failed: 'bg-red-600',
    };
    return `px-2 py-1 rounded-full text-xs font-bold ${colors[status] || 'bg-zinc-600'}`;
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return <div className="text-red-400">Failed to load execution history.</div>;
  }

  if (goals.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500">
        No past orders. Start by issuing a command.
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-20">
      <div className="space-y-2">
        <h2 className="text-4xl font-black tracking-tighter uppercase">Execution History</h2>
        <p className="text-zinc-500 text-lg">Review past and active orders.</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="text-left py-3 px-4 text-xs font-black text-zinc-500 uppercase tracking-widest">Created</th>
              <th className="text-left py-3 px-4 text-xs font-black text-zinc-500 uppercase tracking-widest">Description</th>
              <th className="text-left py-3 px-4 text-xs font-black text-zinc-500 uppercase tracking-widest">Status</th>
              <th className="text-left py-3 px-4 text-xs font-black text-zinc-500 uppercase tracking-widest">Actions</th>
             </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {goals.map(goal => (
              <tr key={goal.id} className="hover:bg-zinc-900/30 transition-colors">
                <td className="py-3 px-4 text-sm text-zinc-400 font-mono">
                  {new Date(goal.createdAt).toLocaleString()}
                </td>
                <td className="py-3 px-4 text-sm text-zinc-300 max-w-md truncate">
                  {goal.description}
                </td>
                <td className="py-3 px-4">
                  <span className={getStatusBadge(goal.status)}>
                    {goal.status.toUpperCase()}
                  </span>
                </td>
                <td className="py-3 px-4">
                  {goal.status === 'planning' || goal.status === 'executing' ? (
                    <button
                      onClick={() => handleCancelClick(goal.id)}
                      className="text-red-400 hover:text-red-300 transition-colors"
                      title="Cancel Order"
                    >
                      <Icons.Trash />
                    </button>
                  ) : (
                    <span className="text-zinc-600 text-xs">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmationModal
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        onConfirm={confirmCancel}
        title="Cancel Order"
        message="Are you sure you want to cancel this order? All associated tasks will be stopped."
        confirmText="Yes, Cancel"
        variant="danger"
      />
    </div>
  );
};
