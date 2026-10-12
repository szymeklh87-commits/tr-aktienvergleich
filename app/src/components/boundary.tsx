import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Notice } from './ui';

/** Fängt unerwartete Fehler einer Ansicht ab, damit nicht die ganze App leer wird.
 * Beim Wechsel der Ansicht (resetKey) wird erneut versucht. */
export class ViewBoundary extends Component<{ resetKey: string; children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.warn('Ansicht fehlgeschlagen', error, info.componentStack);
  }

  componentDidUpdate(previous: Readonly<{ resetKey: string; children: ReactNode }>): void {
    if (previous.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    return (
      <Notice
        tone="error"
        title="Diese Ansicht konnte nicht angezeigt werden"
        actions={
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            Neu laden
          </button>
        }
      >
        <p>{this.state.error.message}</p>
        <p>Die übrigen Ansichten funktionieren weiter. Neu laden behebt vorübergehende Ladefehler.</p>
      </Notice>
    );
  }
}
