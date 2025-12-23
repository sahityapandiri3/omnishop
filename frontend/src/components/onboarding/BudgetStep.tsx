'use client';

import { useState } from 'react';
import { BUDGET_OPTIONS } from '@/config/styles';

interface BudgetStepProps {
  budget: number | null;
  isFlexible: boolean;
  onSelect: (budget: number | null, flexible: boolean) => void;
}

export function BudgetStep({ budget, isFlexible, onSelect }: BudgetStepProps) {
  const [customBudget, setCustomBudget] = useState<string>(
    budget && !BUDGET_OPTIONS.some((opt) => opt.value === budget)
      ? String(budget)
      : ''
  );

  const handlePresetSelect = (value: number) => {
    if (budget === value) {
      // Deselect
      onSelect(null, isFlexible);
    } else {
      setCustomBudget('');
      onSelect(value, false);
    }
  };

  const handleCustomBudgetChange = (value: string) => {
    // Only allow numbers
    const numericValue = value.replace(/[^0-9]/g, '');
    setCustomBudget(numericValue);

    if (numericValue) {
      onSelect(parseInt(numericValue, 10), false);
    } else {
      onSelect(null, isFlexible);
    }
  };

  const handleFlexibleToggle = () => {
    const newFlexible = !isFlexible;
    if (newFlexible) {
      // Clear budget when flexible
      setCustomBudget('');
      onSelect(null, true);
    } else {
      onSelect(budget, false);
    }
  };

  const formatCurrency = (value: number): string => {
    if (value >= 100000) {
      return `₹${(value / 100000).toFixed(value % 100000 === 0 ? 0 : 1)} Lakh`;
    }
    return `₹${value.toLocaleString('en-IN')}`;
  };

  return (
    <div className="flex flex-col items-center">
      {/* Header */}
      <div className="text-center mb-10">
        <h2 className="text-2xl md:text-3xl font-light text-neutral-900 mb-3">
          What's your budget?
        </h2>
        <p className="text-neutral-500 font-light">
          This helps us recommend products in your range
        </p>
      </div>

      {/* Budget Presets */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full max-w-2xl mb-6">
        {BUDGET_OPTIONS.map((option) => {
          const isSelected = budget === option.value && !isFlexible;

          return (
            <button
              key={option.value}
              onClick={() => handlePresetSelect(option.value)}
              disabled={isFlexible}
              className={`p-4 rounded-xl border-2 transition-all duration-200 ${
                isFlexible
                  ? 'opacity-50 cursor-not-allowed border-neutral-200 bg-neutral-50'
                  : isSelected
                  ? 'border-primary-600 bg-primary-50 shadow-md'
                  : 'border-neutral-200 bg-white hover:border-neutral-300 hover:shadow-sm'
              }`}
            >
              <div className="text-lg font-semibold text-neutral-900">
                {option.label}
              </div>
              <div className="text-xs text-neutral-500 mt-1">
                {option.description}
              </div>
            </button>
          );
        })}
      </div>

      {/* Custom Budget Input */}
      <div className="w-full max-w-md mb-6">
        <label className="block text-sm font-medium text-neutral-700 mb-2 text-center">
          Or enter a custom budget
        </label>
        <div className="relative">
          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-neutral-500 font-medium">
            ₹
          </span>
          <input
            type="text"
            value={customBudget}
            onChange={(e) => handleCustomBudgetChange(e.target.value)}
            disabled={isFlexible}
            placeholder="Enter amount"
            className={`w-full pl-8 pr-4 py-3 border-2 rounded-xl text-center text-lg font-medium transition-all ${
              isFlexible
                ? 'bg-neutral-50 border-neutral-200 text-neutral-400 cursor-not-allowed'
                : customBudget
                ? 'border-primary-600 bg-primary-50'
                : 'border-neutral-200 bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100'
            }`}
          />
        </div>
        {customBudget && (
          <p className="text-center text-sm text-neutral-500 mt-2">
            {formatCurrency(parseInt(customBudget, 10))}
          </p>
        )}
      </div>

      {/* Flexible Budget Toggle */}
      <div className="w-full max-w-md">
        <button
          onClick={handleFlexibleToggle}
          className={`w-full p-4 rounded-xl border-2 transition-all duration-200 flex items-center justify-center gap-3 ${
            isFlexible
              ? 'border-primary-600 bg-primary-50'
              : 'border-neutral-200 bg-white hover:border-neutral-300'
          }`}
        >
          <div
            className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
              isFlexible
                ? 'border-primary-600 bg-primary-600'
                : 'border-neutral-300'
            }`}
          >
            {isFlexible && (
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
          <span className="text-neutral-700 font-medium">
            I'm flexible on budget
          </span>
        </button>
        <p className="text-xs text-neutral-400 text-center mt-2">
          We'll show you the best options across all price ranges
        </p>
      </div>
    </div>
  );
}
