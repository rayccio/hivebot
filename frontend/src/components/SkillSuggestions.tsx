import React, { useState, useEffect } from 'react';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';
import { LoadingSpinner } from './LoadingSpinner';
import { toast } from 'react-hot-toast';

interface SkillSuggestion {
  id: string;
  skill_name: string;
  goal_id: string;
  goal_description: string;
  task_id: string;
  task_description: string;
  suggested_by?: string;
  created_at: string;
}

export const SkillSuggestions: React.FC = () => {
  const [suggestions, setSuggestions] = useState<SkillSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState<string | null>(null);

  useEffect(() => {
    loadSuggestions();
  }, []);

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      const data = await orchestratorService.listSkillSuggestions();
      setSuggestions(data);
    } catch (err) {
      console.error('Failed to load skill suggestions', err);
      toast.error('Failed to load suggestions');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSkill = async (suggestionId: string) => {
    setCreating(suggestionId);
    try {
      const newSkill = await orchestratorService.createSkillFromSuggestion(suggestionId);
      toast.success(`Skill "${newSkill.name}" created`);
      await loadSuggestions(); // refresh list
    } catch (err) {
      console.error('Failed to create skill from suggestion', err);
      toast.error('Failed to create skill');
    } finally {
      setCreating(null);
    }
  };

  const handleDeleteSuggestion = async (suggestionId: string) => {
    if (!confirm('Delete this suggestion?')) return;
    try {
      await orchestratorService.deleteSkillSuggestion(suggestionId);
      await loadSuggestions();
      toast.success('Suggestion deleted');
    } catch (err) {
      console.error('Failed to delete suggestion', err);
      toast.error('Failed to delete suggestion');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500 italic">
        No pending skill suggestions.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {suggestions.map(s => (
        <div key={s.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
          <div className="flex items-start justify-between">
            <div>
              <h4 className="text-lg font-bold text-emerald-400">{s.skill_name}</h4>
              <p className="text-sm text-zinc-400 mt-1">{s.task_description}</p>
              <div className="text-xs text-zinc-500 mt-2">
                Goal: {s.goal_description}
              </div>
              <div className="text-[10px] text-zinc-600 mt-1">
                Suggested {new Date(s.created_at).toLocaleString()}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleCreateSkill(s.id)}
                disabled={creating === s.id}
                className="px-3 py-1 bg-emerald-600 text-white rounded-lg text-xs font-black uppercase tracking-widest hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-1"
              >
                {creating === s.id ? (
                  <>
                    <LoadingSpinner size="sm" />
                    Creating...
                  </>
                ) : (
                  'Create Skill'
                )}
              </button>
              <button
                onClick={() => handleDeleteSuggestion(s.id)}
                className="p-2 text-zinc-500 hover:text-red-400"
                title="Delete Suggestion"
              >
                <Icons.Trash />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
