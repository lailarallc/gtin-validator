import styles from './ResultsCTA.module.css'

const KIT_URL = 'https://lailarallc.com/kits/gtin-validator'
const SNAPSHOT_URL = 'https://lailarallc.com/snapshot'

interface Props {
  score: number
  grade: string
  total: number
  criticalCount: number
  warningCount: number
}

// Own-data results: the free check shows counts only, and points to the kit.
export default function ResultsCTA({
  score,
  grade,
  total,
  criticalCount,
  warningCount,
}: Props) {
  // Prefilled summary only. Nothing is uploaded anywhere.
  const body =
    'Hi Shawn,\r\n\r\n' +
    'I ran my GTINs through your free validator and have a question.\r\n\r\n' +
    `Score: ${score} (Grade ${grade})\r\n` +
    `Total GTINs: ${total}\r\n` +
    `Critical issues: ${criticalCount}\r\n` +
    `Warnings: ${warningCount}\r\n\r\n` +
    'My question:\r\n\r\n\r\n' +
    'Thanks,'
  const mailto = `mailto:shawn@lailarallc.com?subject=${encodeURIComponent(
    'GTIN validator question',
  )}&body=${encodeURIComponent(body)}`

  const questions = (
    <a className={styles.questions} href={mailto}>
      Questions? Email me.
    </a>
  )

  if (criticalCount > 0 || warningCount > 0) {
    return (
      <section
        className={`${styles.cta} ${criticalCount > 0 ? styles.critical : styles.warning}`}
      >
        <h2>
          {criticalCount > 0
            ? `${criticalCount} of your GTINs will be rejected.`
            : `${warningCount} of your GTINs need a fix before you submit.`}
        </h2>
        <p>
          This free check counts the problems. The GTIN Validator Kit shows
          every one, row by row, with the corrected GTINs, retailer checklists,
          and a PDF report for your team. It runs on your own computer, so your
          file never leaves it.
        </p>
        <a
          className="btn btn-primary"
          href={`${KIT_URL}?source=gtin-free`}
          target="_blank"
          rel="noopener noreferrer"
        >
          See every issue: GTIN Validator Kit, $149
        </a>
        <a
          className={styles.secondary}
          href={`${SNAPSHOT_URL}?source=gtin-free`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Or have Shawn fix it for you: Data Health Snapshot, $950
        </a>
        {questions}
      </section>
    )
  }

  return (
    <section className={`${styles.cta} ${styles.clean}`}>
      <h2>Your GTINs are clean.</h2>
      <p>
        GTINs are one field. The expensive misses hide in the rest of your
        product master: dimensions, case packs, GDSN records. A Data Health
        Snapshot checks the whole file.
      </p>
      <a
        className="btn btn-primary"
        href={`${SNAPSHOT_URL}?source=gtin-free`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Have Shawn check your full product master: $950
      </a>
      {questions}
    </section>
  )
}

// Sample results: the full report, with the kit as the way to get it for your
// own file.
export function SampleCTA() {
  return (
    <section className={styles.cta}>
      <h2>This is the full report, on sample data.</h2>
      <p>
        The GTIN Validator Kit gives you this report for your own file: every
        issue row by row, the corrected GTINs, retailer checklists, and the PDF.
        It runs on your own computer, so your file never leaves it.
      </p>
      <a
        className="btn btn-primary"
        href={`${KIT_URL}?source=gtin-free-sample`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Get the GTIN Validator Kit: $149
      </a>
      <a
        className={styles.secondary}
        href={`${SNAPSHOT_URL}?source=gtin-free-sample`}
        target="_blank"
        rel="noopener noreferrer"
      >
        Or have Shawn do it: Data Health Snapshot, $950
      </a>
    </section>
  )
}
