/**
 * Validation utilities for forms and data
 */

export const validators = {
  email: (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },

  phone: (phone: string): boolean => {
    const phoneRegex = /^\+?[\d\s\-\(\)]+$/;
    return phoneRegex.test(phone) && phone.replace(/\D/g, '').length >= 10;
  },

  required: (value: any): boolean => {
    if (typeof value === 'string') return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    return value != null && value !== undefined;
  },

  minLength: (value: string, min: number): boolean => {
    return value.length >= min;
  },

  maxLength: (value: string, max: number): boolean => {
    return value.length <= max;
  },

  range: (value: number, min: number, max: number): boolean => {
    return value >= min && value <= max;
  },

  url: (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  },

  price: (price: string | number): boolean => {
    const num = typeof price === 'string' ? parseFloat(price) : price;
    return !isNaN(num) && num >= 0;
  },

  imageFile: (file: File): boolean => {
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    return allowedTypes.includes(file.type);
  },

  fileSize: (file: File, maxMB: number): boolean => {
    const maxBytes = maxMB * 1024 * 1024;
    return file.size <= maxBytes;
  }
};

export const validate = {
  form: <T extends Record<string, any>>(
    data: T,
    rules: Partial<Record<keyof T, Array<(value: any) => boolean | string>>>
  ): { isValid: boolean; errors: Partial<Record<keyof T, string[]>> } => {
    const errors: Partial<Record<keyof T, string[]>> = {};
    let isValid = true;

    for (const [field, fieldRules] of Object.entries(rules)) {
      const value = data[field];
      const fieldErrors: string[] = [];

      for (const rule of fieldRules as Array<(value: any) => boolean | string>) {
        const result = rule(value);
        if (result !== true) {
          fieldErrors.push(typeof result === 'string' ? result : `Invalid ${field}`);
          isValid = false;
        }
      }

      if (fieldErrors.length > 0) {
        errors[field as keyof T] = fieldErrors;
      }
    }

    return { isValid, errors };
  },

  productFilters: (filters: any): boolean => {
    if (filters.min_price !== undefined && filters.max_price !== undefined) {
      return filters.min_price <= filters.max_price;
    }
    return true;
  },

  chatMessage: (message: string): { isValid: boolean; error?: string } => {
    if (!message.trim()) {
      return { isValid: false, error: 'Message cannot be empty' };
    }
    if (message.length > 2000) {
      return { isValid: false, error: 'Message is too long (max 2000 characters)' };
    }
    return { isValid: true };
  }
};

export default validators;