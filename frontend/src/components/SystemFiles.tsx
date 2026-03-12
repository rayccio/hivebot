import React, { useState, useEffect } from 'react';
import { FileEntry } from '../types';
import { Icons } from '../constants';
import { orchestratorService } from '../services/orchestratorService';
import { LoadingSpinner } from './LoadingSpinner';

export const SystemFiles: React.FC = () => {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [globalMd, setGlobalMd] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const filesData = await orchestratorService.listGlobalFiles();
      setFiles(filesData);
      // Load GLOBAL.md content (we'll store it as a file named "GLOBAL.md")
      const mdFile = filesData.find(f => f.name === 'GLOBAL.md');
      if (mdFile) {
        const response = await fetch(orchestratorService.getGlobalFileDownloadUrl('GLOBAL.md'));
        const text = await response.text();
        setGlobalMd(text);
      } else {
        setGlobalMd('');
      }
    } catch (err) {
      console.error('Failed to load system files', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveGlobalMd = async () => {
    setSaving(true);
    try {
      // Convert string to a File object and upload
      const blob = new Blob([globalMd], { type: 'text/markdown' });
      const file = new File([blob], 'GLOBAL.md', { type: 'text/markdown' });
      await orchestratorService.uploadGlobalFile(file);
      await loadData();
    } catch (err) {
      console.error('Failed to save GLOBAL.md', err);
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      await orchestratorService.uploadGlobalFile(file);
      await loadData();
    } catch (err) {
      console.error('File upload failed', err);
    } finally {
      setIsUploading(false);
      if (e.target) e.target.value = '';
    }
  };

  const handleDeleteFile = async (filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      await orchestratorService.deleteGlobalFile(filename);
      await loadData();
    } catch (err) {
      console.error('File deletion failed', err);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="space-y-2">
        <h3 className="text-2xl font-black tracking-tighter uppercase">System Files</h3>
        <p className="text-zinc-500 text-sm">Global knowledge base available to all hives (if access level permits).</p>
      </div>

      {/* GLOBAL.md Editor */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">GLOBAL.md</span>
          <button
            onClick={handleSaveGlobalMd}
            disabled={saving}
            className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-black uppercase tracking-widest hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
          >
            {saving ? (
              <>
                <LoadingSpinner size="sm" />
                Saving...
              </>
            ) : (
              'Save'
            )}
          </button>
        </div>
        <textarea
          value={globalMd}
          onChange={(e) => setGlobalMd(e.target.value)}
          rows={15}
          className="w-full bg-zinc-950 border border-zinc-800 rounded-2xl p-4 font-mono text-sm text-zinc-300 focus:outline-none"
          placeholder="# GLOBAL Knowledge Base"
        />
        <p className="text-xs text-zinc-500 mt-2 italic">
          This content will be embedded and made available to hives with GLOBAL access level.
        </p>
      </div>

      {/* Other System Files */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <span className="text-[10px] font-black text-zinc-500 uppercase tracking-widest">Other Files</span>
          <button
            onClick={() => document.getElementById('system-file-upload')?.click()}
            disabled={isUploading}
            className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-black uppercase tracking-widest hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-2"
          >
            {isUploading ? (
              <>
                <LoadingSpinner size="sm" />
                Uploading...
              </>
            ) : (
              <>
                <Icons.Plus /> Upload File
              </>
            )}
          </button>
          <input
            id="system-file-upload"
            type="file"
            onChange={handleFileUpload}
            className="hidden"
          />
        </div>

        <div className="space-y-2">
          {files.filter(f => f.name !== 'GLOBAL.md').length === 0 ? (
            <p className="text-zinc-500 italic text-center py-8">No system files uploaded.</p>
          ) : (
            files.filter(f => f.name !== 'GLOBAL.md').map(file => (
              <div key={file.id} className="flex items-center justify-between p-3 bg-zinc-950 rounded-xl border border-zinc-800">
                <div className="flex items-center gap-3">
                  <Icons.File className="text-emerald-500" />
                  <span className="text-sm font-medium text-zinc-300">{file.name}</span>
                  <span className="text-[10px] text-zinc-500">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={orchestratorService.getGlobalFileDownloadUrl(file.name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-zinc-500 hover:text-emerald-400 transition-colors"
                    title="Download"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  </a>
                  <button
                    onClick={() => handleDeleteFile(file.name)}
                    className="p-2 text-zinc-500 hover:text-red-500 transition-colors"
                    title="Delete"
                  >
                    <Icons.Trash className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
