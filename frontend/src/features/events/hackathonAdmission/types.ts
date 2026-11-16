import type { ComponentType } from 'react'
import type { ProgrammeContext, ProgrammeMemberInput, AdmissionSelection } from '../contracts/types'
export type { ProgrammeContext, AdmissionSelection }
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export type Application = Omit<import('../../../generated/api').Application, 'form'> & {
  form: ProgrammeContext['application_form']
}
export type AdmissionRequirements = Omit<import('../../../generated/api').AdmissionRequirements, 'host_waiver'> & {
  host_waiver: (NonNullable<import('../../../generated/api').AdmissionRequirements['host_waiver']> & { acceptance_required?: boolean }) | null
}
export type OwnerAdmission = import('../../../generated/api').AdmissionProjection
export type Prefill = import('../../../generated/api').SavedVaultPrefillResponse
export interface FormValue {
  answers: ProgrammeMemberInput['answers']; derivations: ProgrammeMemberInput['derivations']
  save_choices: Record<string, boolean>; saved_detail_versions: Record<string, number>
}
/** F owns rendering, hidden-field rules and profile descriptors; P owns prefill. */
export interface FieldsProps {
  schema: NonNullable<ProgrammeContext['application_form']>; value: FormValue
  onChange: (value: FormValue) => void; prefill: Prefill | undefined
  errors: Record<string, unknown>; disabled: boolean; savedDetailsAvailable: boolean
}
export type FormFields = ComponentType<FieldsProps>
export interface PublicProfile { display_name?: string; url?: string; photo_url?: string }
export type Team = Omit<import('../../../generated/api').Team, 'id'> & { id: number }
export interface FinderCard {
  id: number; event_id: number; version: number; kind: 'person' | 'team'
  name?: string; intro: string; skills: string[]; slots?: number
  profile?: PublicProfile | null; profiles?: PublicProfile[]
}
