import React, { useEffect, useState } from 'react';
import { Hive, HiveMindAccessLevel, HiveMindConfig } from '../types';
import { Icons } from '../constants';

interface HiveBrainProps {
  hive: Hive;
  allHives: Hive[];
  onUpdate: (config: HiveMindConfig) => void;
}

export const HiveBrain: React.FC<HiveBrainProps> = ({ hive, allHives, onUpdate }) => {
  // Local state to hold the config – ensures UI updates immediately on click
  const [config, setConfig] = useState<HiveMindConfig>(
    hive.hiveMindConfig || { accessLevel: HiveMindAccessLevel.ISOLATED, sharedHiveIds: [] }
  );

  // Sync local state when the prop changes (e.g., after external update)
  useEffect(() => {
    setConfig(hive.hiveMindConfig || { accessLevel: HiveMindAccessLevel.ISOLATED, sharedHiveIds: [] });
  }, [hive]);

  const handleAccessLevelChange = (level: HiveMindAccessLevel) => {
    const newConfig = { ...config, accessLevel: level };
    // If switching away from SHARED, clear sharedHiveIds
    if (level !== HiveMindAccessLevel.SHARED) {
      newConfig.sharedHiveIds = [];
    }
    setConfig(newConfig);
    onUpdate(newConfig);
  };

  const toggleSharedHive = (hiveId: string) => {
    const current = config.sharedHiveIds || [];
    const next = current.includes(hiveId)
      ? current.filter(id => id !== hiveId)
      : [...current, hiveId];
    const newConfig = { ...config, sharedHiveIds: next };
    setConfig(newConfig);
    onUpdate(newConfig);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 md:space-y-12 pb-20 animate-in fade-in duration-500">
      <div className="space-y-2">
        <h2 className="text-3xl md:text-5xl font-black tracking-tighter">
          Hive <span className="text-emerald-500">Brain</span>
        </h2>
        <p className="text-zinc-500 text-base md:text-lg">
          Configure how this hive interacts with the global Hive Mind.
        </p>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 space-y-6 shadow-2xl relative overflow-hidden group">
        <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
          <Icons.Layers />
        </div>
        <h3 className="text-xs font-black uppercase tracking-[0.2em] text-emerald-500">
          Access Segmentation
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* ISOLATED */}
          <button
            onClick={() => handleAccessLevelChange(HiveMindAccessLevel.ISOLATED)}
            className={`p-6 rounded-2xl border transition-all text-left space-y-2 ${
              config.accessLevel === HiveMindAccessLevel.ISOLATED
                ? 'bg-emerald-500/10 border-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.1)]'
                : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-widest text-zinc-400">
                Isolated
              </span>
              {config.accessLevel === HiveMindAccessLevel.ISOLATED && (
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
              )}
            </div>
            <p className="text-xs font-bold text-zinc-200">Per‑Hive Brain</p>
            <p className="text-[10px] text-zinc-500 leading-relaxed italic">
              Bots only reference files and history from this hive.
            </p>
          </button>

          {/* SHARED */}
          <button
            onClick={() => handleAccessLevelChange(HiveMindAccessLevel.SHARED)}
            className={`p-6 rounded-2xl border transition-all text-left space-y-2 ${
              config.accessLevel === HiveMindAccessLevel.SHARED
                ? 'bg-blue-500/10 border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.1)]'
                : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-widest text-zinc-400">
                Shared
              </span>
              {config.accessLevel === HiveMindAccessLevel.SHARED && (
                <div className="w-2 h-2 rounded-full bg-blue-500" />
              )}
            </div>
            <p className="text-xs font-bold text-zinc-200">Cross‑Hive Sharing</p>
            <p className="text-[10px] text-zinc-500 leading-relaxed italic">
              Select specific hives to share knowledge with this hive.
            </p>
          </button>

          {/* GLOBAL */}
          <button
            onClick={() => handleAccessLevelChange(HiveMindAccessLevel.GLOBAL)}
            className={`p-6 rounded-2xl border transition-all text-left space-y-2 ${
              config.accessLevel === HiveMindAccessLevel.GLOBAL
                ? 'bg-purple-500/10 border-purple-500 shadow-[0_0_20px_rgba(168,85,247,0.1)]'
                : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-widest text-zinc-400">
                Global
              </span>
              {config.accessLevel === HiveMindAccessLevel.GLOBAL && (
                <div className="w-2 h-2 rounded-full bg-purple-500" />
              )}
            </div>
            <p className="text-xs font-bold text-zinc-200">Super‑Brain Access</p>
            <p className="text-[10px] text-zinc-500 leading-relaxed italic">
              Full access to every file and conversation across all hives.
            </p>
          </button>
        </div>

        {config.accessLevel === HiveMindAccessLevel.SHARED && (
          <div className="mt-6 p-6 bg-zinc-950 border border-zinc-800 rounded-2xl space-y-4 animate-in slide-in-from-top-2 duration-300">
            <h4 className="text-[10px] font-black uppercase tracking-widest text-zinc-500">
              Available Hive Brains
            </h4>
            <div className="flex flex-wrap gap-3">
              {allHives.filter(h => h.id !== hive.id).length === 0 && (
                <p className="text-[10px] text-zinc-600 italic">No other hives available to link.</p>
              )}
              {allHives
                .filter(h => h.id !== hive.id)
                .map(h => (
                  <button
                    key={h.id}
                    onClick={() => toggleSharedHive(h.id)}
                    className={`px-4 py-2 rounded-xl text-[10px] font-bold transition-all border ${
                      (config.sharedHiveIds || []).includes(h.id)
                        ? 'bg-blue-500/20 border-blue-500 text-blue-400'
                        : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:border-zinc-700'
                    }`}
                  >
                    {h.name}
                  </button>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
