import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';
import { Skill, SkillType, SkillVisibility } from '../types';
import { LoadingSpinner } from './LoadingSpinner';
import { toast } from 'react-hot-toast';

interface SkillLibraryProps {
  onInstall?: (skill: Skill) => void;
  showInstall?: boolean;
}

export const SkillLibrary: React.FC<SkillLibraryProps> = ({ onInstall, showInstall = true }) => {
  const [filter, setFilter] = useState('');
  const [selectedType, setSelectedType] = useState<SkillType | ''>('');

  // Fetch skills using React Query
  const { data: skills = [], isLoading, error } = useQuery({
    queryKey: ['skills', 'public'],
    queryFn: () => orchestratorService.listSkills('public'),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  React.useEffect(() => {
    if (error) {
      toast.error('Failed to load skills');
    }
  }, [error]);

  const filteredSkills = skills.filter(skill => {
    if (filter && !skill.name.toLowerCase().includes(filter.toLowerCase()) && !skill.description.toLowerCase().includes(filter.toLowerCase())) return false;
    if (selectedType && skill.type !== selectedType) return false;
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search skills..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
        />
        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value as SkillType | '')}
          className="bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2 text-sm text-zinc-200 focus:border-emerald-500 outline-none"
        >
          <option value="">All types</option>
          {Object.values(SkillType).map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredSkills.map(skill => (
          <div key={skill.id} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 hover:border-emerald-500/30 transition-all">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-bold text-emerald-400">{skill.name}</h3>
                <p className="text-xs text-zinc-500 mt-1">{skill.type}</p>
              </div>
              {showInstall && onInstall && (
                <button
                  onClick={() => onInstall(skill)}
                  className="px-3 py-1 bg-emerald-600 text-white rounded-lg text-xs font-black uppercase tracking-widest hover:bg-emerald-500"
                >
                  Install
                </button>
              )}
            </div>
            <p className="text-sm text-zinc-400 mt-3 line-clamp-3">{skill.description}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {skill.tags.map(tag => (
                <span key={tag} className="px-2 py-1 bg-zinc-800 text-zinc-400 rounded text-[10px] font-mono">#{tag}</span>
              ))}
            </div>
            <div className="mt-4 text-[10px] text-zinc-600">
              v{skill.metadata?.version || '1.0'} • by {skill.authorId || 'community'}
            </div>
          </div>
        ))}
        {filteredSkills.length === 0 && (
          <div className="col-span-full text-center py-12 text-zinc-500 italic">
            No skills found.
          </div>
        )}
      </div>
    </div>
  );
};
