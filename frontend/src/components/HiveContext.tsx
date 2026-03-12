import React, { useState } from 'react';
import { Hive, FileEntry } from '../types';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';

interface HiveContextProps {
  hive: Hive;
  onUpdateHive: (hiveId: string, updates: any) => Promise<Hive>;
}

export const HiveContext: React.FC<HiveContextProps> = ({ hive, onUpdateHive }) => {
  const [isUploading, setIsUploading] = useState(false);

  const handleAddFile = async () => {
    const name = prompt('File name:');
    if (!name) return;
    
    const newFile: FileEntry = {
      id: Math.random().toString(36).substr(2, 9),
      name,
      content: '',
      size: 0,
      type: 'md',
      uploadedAt: new Date().toISOString()
    };
    
    try {
      await orchestratorService.addGlobalFileToHive(hive.id, newFile);
      await onUpdateHive(hive.id, { globalFiles: [...hive.globalFiles, newFile] });
    } catch (err) {
      console.error('Failed to add file', err);
    }
  };

  const handleDeleteFile = async (fileId: string) => {
    try {
      await orchestratorService.removeGlobalFileFromHive(hive.id, fileId);
      await onUpdateHive(hive.id, { globalFiles: hive.globalFiles.filter(f => f.id !== fileId) });
    } catch (err) {
      console.error('Failed to delete file', err);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-20 animate-in fade-in duration-700">
      <div className="space-y-2">
        <h2 className="text-3xl md:text-4xl font-black tracking-tighter text-emerald-500">Hive Context</h2>
        <p className="text-zinc-500 text-sm md:text-base">HIVE.md definitions and hive files inherited by all hive entities.</p>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* HIVE.md Section */}
        <section className="lg:col-span-2 bg-zinc-900 rounded-3xl border border-zinc-800 p-4 md:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-4 px-2">
            <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">HIVE.md Configuration</span>
          </div>
          <textarea 
            value={hive.globalUserMd} 
            onChange={(e) => onUpdateHive(hive.id, { globalUserMd: e.target.value })}
            className="w-full h-[400px] md:h-[500px] bg-transparent text-zinc-300 font-mono text-sm resize-none focus:outline-none border border-zinc-800/50 rounded-2xl p-4 md:p-6 shadow-inner" 
            spellCheck={false} 
          />
        </section>

        {/* Hive Files Section */}
        <section className="bg-zinc-900 rounded-3xl border border-zinc-800 p-6 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Hive Files</span>
            <button 
              onClick={handleAddFile}
              disabled={isUploading}
              className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
            >
              {isUploading ? (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              ) : (
                <Icons.Plus />
              )}
            </button>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto">
            {hive.globalFiles.length === 0 && (
              <p className="text-zinc-600 text-xs italic text-center py-10">No hive files.</p>
            )}
            {hive.globalFiles.map(file => (
              <div key={file.id} className="group flex items-center justify-between p-3 bg-zinc-950 border border-zinc-800 rounded-xl hover:border-emerald-500/30 transition-all">
                <div className="flex items-center gap-3 overflow-hidden">
                  <Icons.File />
                  <span className="text-xs font-bold text-zinc-400 truncate">{file.name}</span>
                </div>
                <button 
                  onClick={() => handleDeleteFile(file.id)}
                  className="p-1.5 text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                >
                  <Icons.Trash />
                </button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};
