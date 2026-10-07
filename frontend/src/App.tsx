import { useCallback, useReducer } from 'react'
import {
  CaseGTINGenerator,
  CheckDigitCorrections,
  CostOfInaction,
  ExecutiveSummary,
  FullItemDetail,
  IssuesBySeverity,
  PackagingHierarchy,
  PrioritizedFixPlan,
  RetailerReadiness,
} from './components/AnalysisSections'
import DownloadReports from './components/DownloadReports'
import Footer from './components/Footer'
import Header from './components/Header'
import HeroSection from './components/HeroSection'
import InputSection from './components/InputSection'
import NavigationSidebar from './components/NavigationSidebar'
import ResultsCTA, { SampleCTA } from './components/ResultsCTA'
import ScoreCard from './components/ScoreCard'
import SummaryStats from './components/SummaryStats'
import { appReducer, initialState } from './reducer'
import { isFullReport } from './types'

export default function App() {
  const [state, dispatch] = useReducer(appReducer, initialState)

  const handleSectionChange = useCallback(
    (id: string) => dispatch({ type: 'SET_ACTIVE_SECTION', section: id }),
    [],
  )

  const data = state.validationData

  return (
    <div className="container">
      <Header />

      {state.phase === 'idle' && <HeroSection />}

      {state.error && (
        <div className="error-banner">
          <span>{state.error}</span>
          <button onClick={() => dispatch({ type: 'START_OVER' })}>
            &times;
          </button>
        </div>
      )}

      {state.phase !== 'results' && (
        <>
          <hr className="divider" />
          <InputSection state={state} dispatch={dispatch} />
        </>
      )}

      {state.phase === 'loading' && (
        <div className="loading-overlay">
          <div className="spinner" />
          <p>Validating your GTINs against GS1 standards...</p>
        </div>
      )}

      {state.phase === 'results' && data && (
        <>
          <button
            className="btn"
            style={{ marginBottom: 'var(--space-md)' }}
            onClick={() => dispatch({ type: 'START_OVER' })}
          >
            Start over
          </button>

          <ScoreCard score={data.score} />
          <SummaryStats summary={data.summary} />

          {!isFullReport(data) && (
            <ResultsCTA
              score={data.score.score}
              grade={data.score.grade}
              total={data.summary.total_gtins}
              criticalCount={data.summary.critical_issues}
              warningCount={data.summary.warnings}
            />
          )}
        </>
      )}

      {state.phase === 'results' && data && isFullReport(data) && (
        <>
          <SampleCTA />

          <hr className="divider" />

          <DownloadReports
            token={data.token}
            companyName={state.companyName}
            onCompanyNameChange={(name) =>
              dispatch({ type: 'SET_COMPANY_NAME', name })
            }
            grade={data.score.grade}
            score={data.score.score}
            criticalCount={data.summary.critical_issues}
          />

          <hr className="divider" />

          <NavigationSidebar
            activeSection={state.activeSection}
            onSectionChange={handleSectionChange}
          >
            <IssuesBySeverity results={data.results} />
            <FullItemDetail results={data.results} />
            <CheckDigitCorrections items={data.before_after} />
            <PackagingHierarchy hierarchy={data.hierarchy} />

            <h2 style={{ marginTop: 'var(--space-xl)', marginBottom: 'var(--space-md)' }}>
              Deep Analysis
            </h2>

            <ExecutiveSummary text={data.executive_summary} />
            <PrioritizedFixPlan items={data.fix_roadmap} />
            <RetailerReadiness
              checklists={data.retailer_checklists}
              selectedRetailer={state.selectedRetailer}
            />
            <CostOfInaction cost={data.cost_estimate} />
            <CaseGTINGenerator suggestions={data.gtin14_suggestions} />
          </NavigationSidebar>
        </>
      )}

      <Footer />
    </div>
  )
}
