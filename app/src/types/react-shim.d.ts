/*
 * Minimale Typdeklarationen für React 19.
 *
 * In der Entwicklungsumgebung dieses Projekts war das Paket @types/react nicht
 * installierbar (kein Registry-Zugang). Diese Datei deklariert genau die verwendeten
 * APIs. Mit installiertem @types/react kann sie gelöscht werden.
 */

declare module 'react' {
  export type Key = string | number | bigint;
  export interface ReactElement<P = any> {
    type: any;
    props: P;
    key: string | null;
  }
  export type ReactNode =
    | ReactElement
    | string
    | number
    | bigint
    | boolean
    | null
    | undefined
    | Iterable<ReactNode>;
  export type Dispatch<A> = (value: A) => void;
  export type SetStateAction<S> = S | ((previous: S) => S);
  export interface RefObject<T> {
    current: T;
  }
  export type RefCallback<T> = (instance: T | null) => void;
  export type Ref<T> = RefObject<T | null> | RefCallback<T> | null;
  export type FC<P = {}> = (props: P) => ReactNode;
  export interface Context<T> {
    Provider: FC<{ value: T; children?: ReactNode }>;
  }
  export type CSSProperties = Record<string, string | number | undefined>;

  export function useState<S>(initial: S | (() => S)): [S, Dispatch<SetStateAction<S>>];
  export function useEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  export function useLayoutEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  export function useMemo<T>(factory: () => T, deps: readonly unknown[]): T;
  export function useCallback<T extends (...args: any[]) => any>(callback: T, deps: readonly unknown[]): T;
  export function useRef<T>(initial: T): RefObject<T>;
  export function useReducer<S, A>(reducer: (state: S, action: A) => S, initial: S): [S, Dispatch<A>];
  export function useContext<T>(context: Context<T>): T;
  export function createContext<T>(defaultValue: T): Context<T>;
  export function useId(): string;
  export function useSyncExternalStore<T>(subscribe: (onChange: () => void) => () => void, getSnapshot: () => T): T;
  export function useDeferredValue<T>(value: T): T;
  export function useTransition(): [boolean, (callback: () => void) => void];
  export function startTransition(callback: () => void): void;
  export function memo<T>(component: T): T;
  export const Fragment: any;
  export const StrictMode: any;
  export const Suspense: any;
  export interface ErrorInfo {
    componentStack?: string | null;
  }
  export class Component<P = {}, S = {}> {
    constructor(props: P);
    readonly props: Readonly<P>;
    state: Readonly<S>;
    setState(state: Partial<S> | ((previous: Readonly<S>, props: Readonly<P>) => Partial<S> | null) | null, callback?: () => void): void;
    forceUpdate(callback?: () => void): void;
    render(): ReactNode;
    componentDidMount?(): void;
    componentDidUpdate?(previousProps: Readonly<P>, previousState: Readonly<S>): void;
    componentWillUnmount?(): void;
    componentDidCatch?(error: Error, info: ErrorInfo): void;
  }
}

declare module 'react/jsx-runtime' {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
  export namespace JSX {
    /* Strukturgleich zu ReactElement (ohne import('react'), das hier auf die untypisierte JS-Datei zeigen würde). */
    interface Element {
      type: any;
      props: any;
      key: string | null;
    }
    /* Komponenten dürfen jeden ReactNode zurückgeben (wie in @types/react). */
    type ElementType = string | ((props: any) => unknown) | (new (props: any) => unknown);
    interface ElementAttributesProperty {
      props: {};
    }
    interface ElementChildrenAttribute {
      children: {};
    }
    interface IntrinsicAttributes {
      key?: string | number | bigint | null;
    }
    interface IntrinsicElements {
      [name: string]: any;
    }
  }
}

declare module 'react-dom/client' {
  export interface Root {
    render(node: unknown): void;
    unmount(): void;
  }
  export function createRoot(container: Element): Root;
}

declare module '*.css';
