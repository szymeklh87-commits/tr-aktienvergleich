/* Alle aktuellen Kaufkandidaten nach der Signalregel (ab 1.21.0): bis zu 100 Aktien mit Status, Einstieg, Stop, Ziel und
 * CRV – dieselben Prüfungen wie auf der Startseite (lib/tradeplan.ts). */

import { BuyCandidates, SignalHero, useBuyCandidates } from '../components/kaufsignal';

export function CandidatesView() {
  const state = useBuyCandidates(100);
  return (
    <div className="view">
      <BuyCandidates state={state} title="Alle aktuellen Kaufkandidaten" more={false} />
      <SignalHero state={state} rulesOnly />
    </div>
  );
}
