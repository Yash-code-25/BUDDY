import { Navigate, Route, Routes } from 'react-router-dom'
import AuditPage from './hr/AuditPage'
import BuddyDetailPage from './hr/BuddyDetailPage'
import BuddyPoolPage from './hr/BuddyPoolPage'
import HomePage from './hr/HomePage'
import HrLayout from './hr/HrLayout'
import InductionPage from './hr/InductionPage'
import MatchReviewPage from './hr/MatchReviewPage'
import QueuePage from './hr/QueuePage'
import ReportsPage from './hr/ReportsPage'
import ClubsPage from './hr/ClubsPage'
import SettingsPage from './hr/SettingsPage'
import LoginPage from './LoginPage'
import AssessmentPage from './pages/AssessmentPage'
import PortalPage from './portal/PortalPage'

export default function App() {
  return (
    <Routes>
      {/* one sign-in page for everyone: Program admins go to /hr, joiners and buddies to /portal */}
      <Route path="/login" element={<LoginPage />} />

      {/* joiners and buddies */}
      <Route path="/portal" element={<PortalPage />} />
      <Route path="/assess/:kind/:token" element={<AssessmentPage />} />

      {/* Program admins */}
      <Route path="/hr" element={<HrLayout />}>
        <Route index element={<HomePage />} />
        <Route path="joiners" element={<QueuePage />} />
        <Route path="joiners/:id" element={<MatchReviewPage />} />
        <Route path="buddies" element={<BuddyPoolPage />} />
        <Route path="buddies/:id" element={<BuddyDetailPage />} />
        <Route path="induction" element={<InductionPage />} />
        <Route path="clubs" element={<ClubsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="audit" element={<AuditPage />} />
      </Route>

      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
