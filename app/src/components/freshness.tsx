/* Hinweis bei einem Problem mit der Aktualisierung (ab 1.17): was passiert ist und was du tun kannst. */

import type { FreshnessProblem } from '../lib/freshness';
import { Notice } from './ui';

export function FreshnessNotice({ problem }: { problem: FreshnessProblem }) {
  return (
    <Notice tone="warn" title={problem.title}>
      <p>{problem.text}</p>
      <p>
        <strong>Was du tun kannst:</strong> {problem.todo}
      </p>
    </Notice>
  );
}
