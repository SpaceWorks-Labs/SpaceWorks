import { CustomFormFields } from '../../forms/CustomFormFields'
import type { CustomAnswers, CustomFormQuestion } from '../../forms/customFormTypes'
import { FEEDBACK_WORDS, WordFeedbackRating } from '../../staff/eventProgramme/WordFeedbackRating'

/** Exact string-option revisions only. Historical numeric ratings keep their own controls. */
export function isWordRating(question: CustomFormQuestion) {
  return question.type === 'single_choice' && question.options.length === 4
    && FEEDBACK_WORDS.every(word => question.options.includes(word))
}
export function EventFeedbackFields({ schema, answers, onChange, errors = {}, yesNoAsCheckbox }: {
  schema: CustomFormQuestion[]; answers: CustomAnswers; onChange: (answers: CustomAnswers) => void; errors?: Record<string, string>; yesNoAsCheckbox?: boolean
}) {
  return <div className="grid gap-5">{schema.map(question => isWordRating(question) ? <div key={question.id}>
    <WordFeedbackRating schemaVersion={1} id={question.id} label={question.label} required={question.required}
      values={{ Excellent: 'Excellent', Good: 'Good', Okay: 'Okay', Poor: 'Poor' }}
      value={typeof answers[question.id] === 'string' ? answers[question.id] as string : undefined}
      onChange={value => onChange({ ...answers, [question.id]: value })} />
    {errors[question.id] ? <p role="alert" className="mt-2 text-sm text-danger">{errors[question.id]}</p> : null}
  </div> : <CustomFormFields key={question.id} schema={[question]} answers={answers} onChange={onChange} errors={errors} yesNoAsCheckbox={yesNoAsCheckbox} />)}</div>
}
