import React from 'react';
import { Icons } from '../constants';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, actions }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 w-full max-w-md space-y-6 shadow-2xl animate-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-black uppercase tracking-tighter">{title}</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors">
            <Icons.X />
          </button>
        </div>
        <div className="text-zinc-300 text-sm">{children}</div>
        {actions && <div className="flex gap-3 pt-4">{actions}</div>}
      </div>
    </div>
  );
};

interface AlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  message: string;
  confirmText?: string;
  onConfirm?: () => void;
  variant?: 'warning' | 'error' | 'info';
}

export const AlertModal: React.FC<AlertModalProps> = ({
  isOpen,
  onClose,
  title,
  message,
  confirmText = 'OK',
  onConfirm,
  variant = 'warning'
}) => {
  const iconColor = {
    warning: 'text-yellow-500',
    error: 'text-red-500',
    info: 'text-blue-500'
  }[variant];

  const Icon = variant === 'warning' ? Icons.Alert : variant === 'error' ? Icons.Alert : Icons.Info;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <div className="flex items-center gap-3">
        <div className={`text-2xl ${iconColor}`}>
          <Icon />
        </div>
        <p className="text-zinc-300">{message}</p>
      </div>
      <div className="flex justify-end gap-3 mt-6">
        <button
          onClick={() => {
            if (onConfirm) onConfirm();
            onClose();
          }}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-black uppercase tracking-widest transition-all"
        >
          {confirmText}
        </button>
      </div>
    </Modal>
  );
};

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning';
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'warning'
}) => {
  const confirmClass = variant === 'danger'
    ? 'bg-red-600 hover:bg-red-500'
    : 'bg-yellow-600 hover:bg-yellow-500';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <p className="text-zinc-300">{message}</p>
      <div className="flex justify-end gap-3 mt-6">
        <button
          onClick={onClose}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-black uppercase tracking-widest transition-all"
        >
          {cancelText}
        </button>
        <button
          onClick={() => {
            onConfirm();
            onClose();
          }}
          className={`px-4 py-2 ${confirmClass} text-white rounded-xl text-xs font-black uppercase tracking-widest transition-all`}
        >
          {confirmText}
        </button>
      </div>
    </Modal>
  );
};
