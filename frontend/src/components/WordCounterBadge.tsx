import React from 'react';
import { countVietnameseWords } from '../api';
import { CheckCircle2, AlertTriangle, AlertCircle } from 'lucide-react';

interface WordCounterBadgeProps {
  text: string;
  target?: number;
  showIcon?: boolean;
}

export const WordCounterBadge: React.FC<WordCounterBadgeProps> = ({
  text,
  target = 42,
  showIcon = true
}) => {
  const count = countVietnameseWords(text);
  const diff = count - target;

  if (count >= target && count <= 60) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 badge-exact-42">
        {showIcon && <CheckCircle2 className="w-3.5 h-3.5" />}
        <span>{count} từ (≥{target} từ)</span>
        <span className="text-[10px] bg-emerald-500/20 px-1.5 py-0.5 rounded text-emerald-300">Trọn câu 10s</span>
      </span>
    );
  }

  if (count < target) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        {showIcon && <AlertTriangle className="w-3.5 h-3.5" />}
        <span>{count}/{target}+ từ</span>
        <span className="text-[10px] bg-amber-500/20 px-1.5 py-0.5 rounded text-amber-300">Thiếu {Math.abs(diff)} từ</span>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
      {showIcon && <AlertCircle className="w-3.5 h-3.5" />}
      <span>{count} từ</span>
      <span className="text-[10px] bg-amber-500/20 px-1.5 py-0.5 rounded text-amber-300">Hơi dài cho 10s</span>
    </span>
  );
};
