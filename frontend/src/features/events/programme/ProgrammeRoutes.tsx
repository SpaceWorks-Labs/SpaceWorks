import { Route, Routes, useLocation, useParams } from 'react-router-dom'
import { EventProgrammePage } from './EventProgrammePage'
import { ProgrammeAccess } from './ProgrammeAccess'
import { programmeRoutePaths, programmeAccountPaths } from './routeNames'
import { SavedDetailsPage } from '../../accountSavedDetails/SavedDetailsPage'
import { SecurityActivityPage } from '../../accountActivity/SecurityActivityPage'
import { CertificateVerificationPage } from '../eventPresentation/CertificateVerificationPage'
import { PublicProgrammePage } from './PublicProgrammePage'
import { useTenant } from '../../../lib/tenant'

function ProgrammeAccountPage() {
  const { slug } = useParams(), tenant = useTenant(), location = useLocation()
  return <ProgrammeAccess slug={slug ?? tenant.slug}>{user => /\/security-activity\/?$/.test(location.pathname)
    ? <SecurityActivityPage /> : <SavedDetailsPage actorId={user.id} />}</ProgrammeAccess>
}
export function ProgrammeRoutes() {
  return <Routes>
    {programmeRoutePaths.map(path => <Route path={path} element={<EventProgrammePage />} key={path} />)}
    {programmeAccountPaths.map(path => <Route path={path} element={<ProgrammeAccountPage />} key={path} />)}
    <Route path="/certificates/verify/:verificationId" element={<CertificateVerificationPage />} />
    {['/events/:publicToken', '/m/:slug/events/:publicToken'].flatMap(base => [
      <Route key={`${base}/gallery`} path={`${base}/gallery`} element={<PublicProgrammePage />} />,
      <Route key={`${base}/gallery/:entryPublicId`} path={`${base}/gallery/:entryPublicId`} element={<PublicProgrammePage />} />,
      <Route key={`${base}/results`} path={`${base}/results`} element={<PublicProgrammePage results />} />,
    ])}
  </Routes>
}
