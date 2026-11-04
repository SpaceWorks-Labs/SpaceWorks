import { Fragment, useEffect, useState, type ReactNode } from 'react';
import { onSessionCleared } from '../../../lib/api/sessionContext';

/** Scope/session changes destroy local drafts as well as the protected query cache. */
export function PrivateProgrammeBoundary({ identity, children }: { identity: string; children: ReactNode }) {
  const [epoch, setEpoch] = useState(0);
  useEffect(() => onSessionCleared(() => setEpoch(value => value + 1)), []);
  return <Fragment key={`${identity}:${epoch}`}>{children}</Fragment>;
}
