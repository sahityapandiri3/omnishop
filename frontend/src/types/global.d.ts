/**
 * Global type declarations for external libraries and modules
 */

// Fabric.js types
declare module 'fabric' {
  export interface Canvas {
    new (element: HTMLCanvasElement | string, options?: any): Canvas;
    add(object: any): Canvas;
    remove(object: any): Canvas;
    clear(): Canvas;
    renderAll(): Canvas;
    setWidth(width: number): Canvas;
    setHeight(height: number): Canvas;
    dispose(): void;
  }

  export interface Object {
    set(options: any): Object;
    on(eventName: string, handler: Function): Object;
  }

  export interface Image {
    new (element: HTMLImageElement | string, callback?: Function): Image;
  }

  export const fabric: {
    Canvas: typeof Canvas;
    Object: typeof Object;
    Image: typeof Image;
    [key: string]: any;
  };
}

// Konva types
declare module 'konva' {
  export interface Stage {
    new (config: any): Stage;
    add(layer: any): Stage;
    draw(): void;
    destroy(): void;
  }

  export interface Layer {
    new (config?: any): Layer;
    add(shape: any): Layer;
    draw(): void;
  }

  export interface Rect {
    new (config: any): Rect;
  }

  export interface Circle {
    new (config: any): Circle;
  }

  export interface Image {
    new (config: any): Image;
  }

  export const Konva: {
    Stage: typeof Stage;
    Layer: typeof Layer;
    Rect: typeof Rect;
    Circle: typeof Circle;
    Image: typeof Image;
    [key: string]: any;
  };
}

// React Konva types
declare module 'react-konva' {
  import { ComponentType } from 'react';

  export const Stage: ComponentType<any>;
  export const Layer: ComponentType<any>;
  export const Rect: ComponentType<any>;
  export const Circle: ComponentType<any>;
  export const Image: ComponentType<any>;
  export const Text: ComponentType<any>;
  export const Group: ComponentType<any>;
}

// Environment variables
declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: 'development' | 'production' | 'test';
    NEXT_PUBLIC_API_URL: string;
    NEXT_PUBLIC_APP_NAME: string;
    NEXT_PUBLIC_APP_DESCRIPTION: string;
    NEXT_PUBLIC_API_TIMEOUT: string;
    NEXT_PUBLIC_ENABLE_ANALYTICS: string;
    NEXT_PUBLIC_ENABLE_CHAT: string;
    NEXT_PUBLIC_ENABLE_VISUALIZATION: string;
    NEXT_TELEMETRY_DISABLED: string;
  }
}

// Window object extensions
declare global {
  interface Window {
    gtag?: Function;
    dataLayer?: any[];
    analytics?: any;
  }
}

// CSS Module declarations
declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}

declare module '*.module.scss' {
  const classes: { [key: string]: string };
  export default classes;
}

// Image file declarations
declare module '*.png' {
  const src: string;
  export default src;
}

declare module '*.jpg' {
  const src: string;
  export default src;
}

declare module '*.jpeg' {
  const src: string;
  export default src;
}

declare module '*.gif' {
  const src: string;
  export default src;
}

declare module '*.svg' {
  const src: string;
  export default src;
}

declare module '*.webp' {
  const src: string;
  export default src;
}

// Other file types
declare module '*.md' {
  const content: string;
  export default content;
}

export {};