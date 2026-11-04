"""Frozen cross-lane ownership, immutable history and mapped-write backstops."""
from django.db import migrations

FORWARD_SQL = r"""
CREATE FUNCTION events_eventbroadcastpreview_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_eventbroadcast p2 WHERE p2.id=NEW.campaign_id);
  IF NEW.campaign_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventbroadcast r WHERE r.id=NEW.campaign_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme campaign event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventbroadcastpreview_programme_scope BEFORE INSERT OR UPDATE ON events_eventbroadcastpreview FOR EACH ROW EXECUTE FUNCTION events_eventbroadcastpreview_scope_guard();
CREATE FUNCTION events_eventanswerderivation_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.registration_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme registration event mismatch'; END IF;
  IF NEW.application_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme application event mismatch'; END IF;
  IF NEW.role_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.role_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme role_assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventanswerderivation_programme_scope BEFORE INSERT OR UPDATE ON events_eventanswerderivation FOR EACH ROW EXECUTE FUNCTION events_eventanswerderivation_scope_guard();
CREATE FUNCTION events_certificateissuebatchitem_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_certificateissuebatch p2 WHERE p2.id=NEW.batch_id);
  IF NEW.batch_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_certificateissuebatch r WHERE r.id=NEW.batch_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme batch event mismatch'; END IF;
  IF NEW.certificate_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventattendancecertificate r WHERE r.id=NEW.certificate_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme certificate event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_certificateissuebatchitem_programme_scope BEFORE INSERT OR UPDATE ON events_certificateissuebatchitem FOR EACH ROW EXECUTE FUNCTION events_certificateissuebatchitem_scope_guard();
CREATE FUNCTION events_badgeprintjob_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.template_revision_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventbadgetemplaterevision r WHERE r.id=NEW.template_revision_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme template_revision event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_badgeprintjob_programme_scope BEFORE INSERT OR UPDATE ON events_badgeprintjob FOR EACH ROW EXECUTE FUNCTION events_badgeprintjob_scope_guard();
CREATE FUNCTION events_badgeprintresource_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_badgeprintjob p2 WHERE p2.id=NEW.job_id);
  IF NEW.job_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_badgeprintjob r WHERE r.id=NEW.job_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme job event mismatch'; END IF;
  IF NEW.registration_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme registration event mismatch'; END IF;
  IF NEW.credential_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistrationcredential r WHERE r.id=NEW.credential_id AND (SELECT p2.event_id FROM events_eventregistration p2 WHERE p2.id=r.registration_id)=owner_event) THEN RAISE EXCEPTION 'programme credential event mismatch'; END IF;
  IF NEW.presentation_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventmemberpresentation r WHERE r.id=NEW.presentation_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme presentation event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_badgeprintresource_programme_scope BEFORE INSERT OR UPDATE ON events_badgeprintresource FOR EACH ROW EXECUTE FUNCTION events_badgeprintresource_scope_guard();
CREATE FUNCTION events_eventcontributoradmission_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  IF NEW.registration_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme registration event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcontributoradmission_programme_scope BEFORE INSERT OR UPDATE ON events_eventcontributoradmission FOR EACH ROW EXECUTE FUNCTION events_eventcontributoradmission_scope_guard();
CREATE FUNCTION events_eventcontributornotice_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.signup_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshiftsignup r WHERE r.id=NEW.signup_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme signup event mismatch'; END IF;
  IF NEW.booking_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_officehoursbooking r WHERE r.id=NEW.booking_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme booking event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcontributornotice_programme_scope BEFORE INSERT OR UPDATE ON events_eventcontributornotice FOR EACH ROW EXECUTE FUNCTION events_eventcontributornotice_scope_guard();
CREATE FUNCTION events_eventroleanswerrevision_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventroleanswerrevision_programme_scope BEFORE INSERT OR UPDATE ON events_eventroleanswerrevision FOR EACH ROW EXECUTE FUNCTION events_eventroleanswerrevision_scope_guard();
CREATE FUNCTION events_eventrequirementoverride_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  IF NEW.shift_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshift r WHERE r.id=NEW.shift_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme shift event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventrequirementoverride_programme_scope BEFORE INSERT OR UPDATE ON events_eventrequirementoverride FOR EACH ROW EXECUTE FUNCTION events_eventrequirementoverride_scope_guard();
CREATE FUNCTION events_eventroleposting_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventroleposting_programme_scope BEFORE INSERT OR UPDATE ON events_eventroleposting FOR EACH ROW EXECUTE FUNCTION events_eventroleposting_scope_guard();
CREATE FUNCTION events_eventroleassignment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.posting_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleposting r WHERE r.id=NEW.posting_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme posting event mismatch'; END IF;
  IF NEW.sponsor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventsponsor r WHERE r.id=NEW.sponsor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme sponsor event mismatch'; END IF;
  IF NEW.presentation_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventmemberpresentation r WHERE r.id=NEW.presentation_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme presentation event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventroleassignment_programme_scope BEFORE INSERT OR UPDATE ON events_eventroleassignment FOR EACH ROW EXECUTE FUNCTION events_eventroleassignment_scope_guard();
CREATE FUNCTION events_eventgrantentitlement_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.role_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.role_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme role_assignment event mismatch'; END IF;
  IF NEW.shift_signup_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshiftsignup r WHERE r.id=NEW.shift_signup_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme shift_signup event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventgrantentitlement_programme_scope BEFORE INSERT OR UPDATE ON events_eventgrantentitlement FOR EACH ROW EXECUTE FUNCTION events_eventgrantentitlement_scope_guard();
CREATE FUNCTION events_eventsponsor_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventsponsor_programme_scope BEFORE INSERT OR UPDATE ON events_eventsponsor FOR EACH ROW EXECUTE FUNCTION events_eventsponsor_scope_guard();
CREATE FUNCTION events_eventsponsortrack_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.sponsor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventsponsor r WHERE r.id=NEW.sponsor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme sponsor event mismatch'; END IF;
  IF NEW.track_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathontrack r WHERE r.id=NEW.track_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme track event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventsponsortrack_programme_scope BEFORE INSERT OR UPDATE ON events_eventsponsortrack FOR EACH ROW EXECUTE FUNCTION events_eventsponsortrack_scope_guard();
CREATE FUNCTION events_eventshift_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.posting_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleposting r WHERE r.id=NEW.posting_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme posting event mismatch'; END IF;
  IF NEW.mentor_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor_assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventshift_programme_scope BEFORE INSERT OR UPDATE ON events_eventshift FOR EACH ROW EXECUTE FUNCTION events_eventshift_scope_guard();
CREATE FUNCTION events_eventshiftsignup_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.shift_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshift r WHERE r.id=NEW.shift_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme shift event mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventshiftsignup_programme_scope BEFORE INSERT OR UPDATE ON events_eventshiftsignup FOR EACH ROW EXECUTE FUNCTION events_eventshiftsignup_scope_guard();
CREATE FUNCTION events_eventshiftattendance_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.signup_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshiftsignup r WHERE r.id=NEW.signup_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme signup event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventshiftattendance_programme_scope BEFORE INSERT OR UPDATE ON events_eventshiftattendance FOR EACH ROW EXECUTE FUNCTION events_eventshiftattendance_scope_guard();
CREATE FUNCTION events_eventcontributionhours_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.signup_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshiftsignup r WHERE r.id=NEW.signup_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme signup event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcontributionhours_programme_scope BEFORE INSERT OR UPDATE ON events_eventcontributionhours FOR EACH ROW EXECUTE FUNCTION events_eventcontributionhours_scope_guard();
CREATE FUNCTION events_eventcontributionhoursentry_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.hours_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventcontributionhours r WHERE r.id=NEW.hours_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme hours event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcontributionhoursentry_programme_scope BEFORE INSERT OR UPDATE ON events_eventcontributionhoursentry FOR EACH ROW EXECUTE FUNCTION events_eventcontributionhoursentry_scope_guard();
CREATE FUNCTION events_eventshiftattendancecorrection_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.attendance_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshiftattendance r WHERE r.id=NEW.attendance_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme attendance event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventshiftattendancecorrection_programme_scope BEFORE INSERT OR UPDATE ON events_eventshiftattendancecorrection FOR EACH ROW EXECUTE FUNCTION events_eventshiftattendancecorrection_scope_guard();
CREATE FUNCTION events_eventregistrationcredential_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_eventregistration p2 WHERE p2.id=NEW.registration_id);
  IF NEW.registration_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme registration event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventregistrationcredential_programme_scope BEFORE INSERT OR UPDATE ON events_eventregistrationcredential FOR EACH ROW EXECUTE FUNCTION events_eventregistrationcredential_scope_guard();
CREATE FUNCTION events_hackathonconfig_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.gallery_publication_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_gallerypublication r WHERE r.id=NEW.gallery_publication_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme gallery_publication event mismatch'; END IF;
  IF NEW.results_revision_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.results_revision_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme results_revision event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonconfig_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonconfig FOR EACH ROW EXECUTE FUNCTION events_hackathonconfig_scope_guard();
CREATE FUNCTION events_hackathonapplicationcohort_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonapplicationcohort_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonapplicationcohort FOR EACH ROW EXECUTE FUNCTION events_hackathonapplicationcohort_scope_guard();
CREATE FUNCTION events_hackathonapplication_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.registration_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration r WHERE r.id=NEW.registration_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme registration event mismatch'; END IF;
  IF NEW.cohort_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplicationcohort r WHERE r.id=NEW.cohort_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme cohort event mismatch'; END IF;
  IF NEW.notified_decision_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_applicationdecision r WHERE r.id=NEW.notified_decision_id AND (SELECT p2.event_id FROM events_hackathonapplication p2 WHERE p2.id=r.application_id)=owner_event) THEN RAISE EXCEPTION 'programme notified_decision event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonapplication_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonapplication FOR EACH ROW EXECUTE FUNCTION events_hackathonapplication_scope_guard();
CREATE FUNCTION events_hackathonapplicationanswerrevision_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonapplication p2 WHERE p2.id=NEW.application_id);
  IF NEW.application_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme application event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonapplicationanswerrevision_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonapplicationanswerrevision FOR EACH ROW EXECUTE FUNCTION events_hackathonapplicationanswerrevision_scope_guard();
CREATE FUNCTION events_applicationreviewassignment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.application_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme application event mismatch'; END IF;
  IF NEW.cohort_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplicationcohort r WHERE r.id=NEW.cohort_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme cohort event mismatch'; END IF;
  IF NEW.reviewer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.reviewer_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_applicationreviewassignment_programme_scope BEFORE INSERT OR UPDATE ON events_applicationreviewassignment FOR EACH ROW EXECUTE FUNCTION events_applicationreviewassignment_scope_guard();
CREATE FUNCTION events_applicationreview_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_applicationreviewassignment p2 WHERE p2.id=NEW.assignment_id);
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_applicationreviewassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_applicationreview_programme_scope BEFORE INSERT OR UPDATE ON events_applicationreview FOR EACH ROW EXECUTE FUNCTION events_applicationreview_scope_guard();
CREATE FUNCTION events_applicationreviewconflict_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.application_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme application event mismatch'; END IF;
  IF NEW.cohort_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplicationcohort r WHERE r.id=NEW.cohort_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme cohort event mismatch'; END IF;
  IF NEW.reviewer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.reviewer_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_applicationreviewconflict_programme_scope BEFORE INSERT OR UPDATE ON events_applicationreviewconflict FOR EACH ROW EXECUTE FUNCTION events_applicationreviewconflict_scope_guard();
CREATE FUNCTION events_applicationdecision_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonapplication p2 WHERE p2.id=NEW.application_id);
  IF NEW.batch_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_applicationdecisionbatch r WHERE r.id=NEW.batch_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme batch event mismatch'; END IF;
  IF NEW.application_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme application event mismatch'; END IF;
  IF NEW.cohort_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplicationcohort r WHERE r.id=NEW.cohort_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme cohort event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_applicationdecision_programme_scope BEFORE INSERT OR UPDATE ON events_applicationdecision FOR EACH ROW EXECUTE FUNCTION events_applicationdecision_scope_guard();
CREATE FUNCTION events_hackathonteam_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.leader_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.leader_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonteam_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonteam FOR EACH ROW EXECUTE FUNCTION events_hackathonteam_scope_guard();
CREATE FUNCTION events_hackathonteammember_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.application_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonapplication r WHERE r.id=NEW.application_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme application event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonteammember_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonteammember FOR EACH ROW EXECUTE FUNCTION events_hackathonteammember_scope_guard();
CREATE FUNCTION events_hackathonteaminvite_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonteam p2 WHERE p2.id=NEW.team_id);
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonteaminvite_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonteaminvite FOR EACH ROW EXECUTE FUNCTION events_hackathonteaminvite_scope_guard();
CREATE FUNCTION events_hackathonfinderprofile_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonfinderprofile_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonfinderprofile FOR EACH ROW EXECUTE FUNCTION events_hackathonfinderprofile_scope_guard();
CREATE FUNCTION events_teamcomment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonteam p2 WHERE p2.id=NEW.team_id);
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_teamcomment_programme_scope BEFORE INSERT OR UPDATE ON events_teamcomment FOR EACH ROW EXECUTE FUNCTION events_teamcomment_scope_guard();
CREATE FUNCTION events_hackathonteamexception_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonteam p2 WHERE p2.id=NEW.team_id);
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonteamexception_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonteamexception FOR EACH ROW EXECUTE FUNCTION events_hackathonteamexception_scope_guard();
CREATE FUNCTION events_participantsponsorresumeconsent_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.sponsor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventsponsor r WHERE r.id=NEW.sponsor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme sponsor event mismatch'; END IF;
  IF NEW.participant_asset_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonparticipantasset r WHERE r.id=NEW.participant_asset_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme participant_asset event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_participantsponsorresumeconsent_programme_scope BEFORE INSERT OR UPDATE ON events_participantsponsorresumeconsent FOR EACH ROW EXECUTE FUNCTION events_participantsponsorresumeconsent_scope_guard();
CREATE FUNCTION events_sponsorresumeconsenthistory_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_participantsponsorresumeconsent p2 WHERE p2.id=NEW.consent_id);
  IF NEW.consent_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_participantsponsorresumeconsent r WHERE r.id=NEW.consent_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme consent event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_sponsorresumeconsenthistory_programme_scope BEFORE INSERT OR UPDATE ON events_sponsorresumeconsenthistory FOR EACH ROW EXECUTE FUNCTION events_sponsorresumeconsenthistory_scope_guard();
CREATE FUNCTION events_hackathonprize_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.track_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathontrack r WHERE r.id=NEW.track_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme track event mismatch'; END IF;
  IF NEW.sponsor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventsponsor r WHERE r.id=NEW.sponsor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme sponsor event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonprize_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonprize FOR EACH ROW EXECUTE FUNCTION events_hackathonprize_scope_guard();
CREATE FUNCTION events_judginground_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.coverage_exception_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.coverage_exception_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme coverage_exception event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judginground_programme_scope BEFORE INSERT OR UPDATE ON events_judginground FOR EACH ROW EXECUTE FUNCTION events_judginground_scope_guard();
CREATE FUNCTION events_judgingcriterion_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_judginground p2 WHERE p2.id=NEW.round_id);
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgingcriterion_programme_scope BEFORE INSERT OR UPDATE ON events_judgingcriterion FOR EACH ROW EXECUTE FUNCTION events_judgingcriterion_scope_guard();
CREATE FUNCTION events_eventresultrevision_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.correction_of_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.correction_of_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme correction_of event mismatch'; END IF;
  IF NEW.reason_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.reason_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme reason event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventresultrevision_programme_scope BEFORE INSERT OR UPDATE ON events_eventresultrevision FOR EACH ROW EXECUTE FUNCTION events_eventresultrevision_scope_guard();
CREATE FUNCTION events_eventresultround_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_eventresultrevision p2 WHERE p2.id=NEW.result_id);
  IF NEW.result_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.result_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme result event mismatch'; END IF;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventresultround_programme_scope BEFORE INSERT OR UPDATE ON events_eventresultround FOR EACH ROW EXECUTE FUNCTION events_eventresultround_scope_guard();
CREATE FUNCTION events_eventaward_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_eventresultrevision p2 WHERE p2.id=NEW.result_id);
  IF NEW.result_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.result_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme result event mismatch'; END IF;
  IF NEW.prize_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonprize r WHERE r.id=NEW.prize_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme prize event mismatch'; END IF;
  IF NEW.submission_snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.submission_snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme submission_snapshot event mismatch'; END IF;
  IF NEW.reason_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.reason_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme reason event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventaward_programme_scope BEFORE INSERT OR UPDATE ON events_eventaward FOR EACH ROW EXECUTE FUNCTION events_eventaward_scope_guard();
CREATE FUNCTION events_resultannouncement_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.result_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.result_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme result event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_resultannouncement_programme_scope BEFORE INSERT OR UPDATE ON events_resultannouncement FOR EACH ROW EXECUTE FUNCTION events_resultannouncement_scope_guard();
CREATE FUNCTION events_resultpublicationstate_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.current_announcement_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_resultannouncement r WHERE r.id=NEW.current_announcement_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme current_announcement event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_resultpublicationstate_programme_scope BEFORE INSERT OR UPDATE ON events_resultpublicationstate FOR EACH ROW EXECUTE FUNCTION events_resultpublicationstate_scope_guard();
CREATE FUNCTION events_sponsorwinnerproposal_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.prize_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonprize r WHERE r.id=NEW.prize_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme prize event mismatch'; END IF;
  IF NEW.submission_snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.submission_snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme submission_snapshot event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_sponsorwinnerproposal_programme_scope BEFORE INSERT OR UPDATE ON events_sponsorwinnerproposal FOR EACH ROW EXECUTE FUNCTION events_sponsorwinnerproposal_scope_guard();
CREATE FUNCTION events_judgingreason_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgingreason_programme_scope BEFORE INSERT OR UPDATE ON events_judgingreason FOR EACH ROW EXECUTE FUNCTION events_judgingreason_scope_guard();
CREATE FUNCTION events_judgeassignment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NEW.judge_role_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.judge_role_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme judge_role_assignment event mismatch'; END IF;
  IF NEW.submission_snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.submission_snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme submission_snapshot event mismatch'; END IF;
  IF NEW.track_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathontrack r WHERE r.id=NEW.track_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme track event mismatch'; END IF;
  IF NEW.reason_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.reason_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme reason event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgeassignment_programme_scope BEFORE INSERT OR UPDATE ON events_judgeassignment FOR EACH ROW EXECUTE FUNCTION events_judgeassignment_scope_guard();
CREATE FUNCTION events_judgingroundproject_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_judginground p2 WHERE p2.id=NEW.round_id);
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgingroundproject_programme_scope BEFORE INSERT OR UPDATE ON events_judgingroundproject FOR EACH ROW EXECUTE FUNCTION events_judgingroundproject_scope_guard();
CREATE FUNCTION events_judgescore_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgeassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgescore_programme_scope BEFORE INSERT OR UPDATE ON events_judgescore FOR EACH ROW EXECUTE FUNCTION events_judgescore_scope_guard();
CREATE FUNCTION events_judgerankingballot_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NEW.judge_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.judge_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme judge event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgerankingballot_programme_scope BEFORE INSERT OR UPDATE ON events_judgerankingballot FOR EACH ROW EXECUTE FUNCTION events_judgerankingballot_scope_guard();
CREATE FUNCTION events_judgerankingchoice_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_judgeassignment p2 WHERE p2.id=NEW.assignment_id);
  IF NEW.ballot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgerankingballot r WHERE r.id=NEW.ballot_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme ballot event mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgeassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgerankingchoice_programme_scope BEFORE INSERT OR UPDATE ON events_judgerankingchoice FOR EACH ROW EXECUTE FUNCTION events_judgerankingchoice_scope_guard();
CREATE FUNCTION events_judgeconflict_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judginground r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NEW.reason_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.reason_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme reason event mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgeconflict_programme_scope BEFORE INSERT OR UPDATE ON events_judgeconflict FOR EACH ROW EXECUTE FUNCTION events_judgeconflict_scope_guard();
CREATE FUNCTION events_mentorassignmentrun_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorassignmentrun_programme_scope BEFORE INSERT OR UPDATE ON events_mentorassignmentrun FOR EACH ROW EXECUTE FUNCTION events_mentorassignmentrun_scope_guard();
CREATE FUNCTION events_mentorattentionpreference_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorattentionpreference_programme_scope BEFORE INSERT OR UPDATE ON events_mentorattentionpreference FOR EACH ROW EXECUTE FUNCTION events_mentorattentionpreference_scope_guard();
CREATE FUNCTION events_mentorprofile_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorprofile_programme_scope BEFORE INSERT OR UPDATE ON events_mentorprofile FOR EACH ROW EXECUTE FUNCTION events_mentorprofile_scope_guard();
CREATE FUNCTION events_mentorteamassignment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.mentor_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor_assignment event mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorteamassignment_programme_scope BEFORE INSERT OR UPDATE ON events_mentorteamassignment FOR EACH ROW EXECUTE FUNCTION events_mentorteamassignment_scope_guard();
CREATE FUNCTION events_eventhelptype_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventhelptype_programme_scope BEFORE INSERT OR UPDATE ON events_eventhelptype FOR EACH ROW EXECUTE FUNCTION events_eventhelptype_scope_guard();
CREATE FUNCTION events_eventhelprequest_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.type_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventhelptype r WHERE r.id=NEW.type_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme type event mismatch'; END IF;
  IF NEW.raised_by_role_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.raised_by_role_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme raised_by_role_assignment event mismatch'; END IF;
  IF NEW.claimed_by_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.claimed_by_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme claimed_by event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventhelprequest_programme_scope BEFORE INSERT OR UPDATE ON events_eventhelprequest FOR EACH ROW EXECUTE FUNCTION events_eventhelprequest_scope_guard();
CREATE FUNCTION events_eventhelpaction_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.request_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventhelprequest r WHERE r.id=NEW.request_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme request event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventhelpaction_programme_scope BEFORE INSERT OR UPDATE ON events_eventhelpaction FOR EACH ROW EXECUTE FUNCTION events_eventhelpaction_scope_guard();
CREATE FUNCTION events_eventhelpcomment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.request_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventhelprequest r WHERE r.id=NEW.request_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme request event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventhelpcomment_programme_scope BEFORE INSERT OR UPDATE ON events_eventhelpcomment FOR EACH ROW EXECUTE FUNCTION events_eventhelpcomment_scope_guard();
CREATE FUNCTION events_officehoursbooking_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.slot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshift r WHERE r.id=NEW.slot_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme slot event mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.mentor_assignment_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_assignment_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor_assignment event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_officehoursbooking_programme_scope BEFORE INSERT OR UPDATE ON events_officehoursbooking FOR EACH ROW EXECUTE FUNCTION events_officehoursbooking_scope_guard();
CREATE FUNCTION events_officehourschange_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.slot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventshift r WHERE r.id=NEW.slot_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme slot event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_officehourschange_programme_scope BEFORE INSERT OR UPDATE ON events_officehourschange FOR EACH ROW EXECUTE FUNCTION events_officehourschange_scope_guard();
CREATE FUNCTION events_mentorround_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorround_programme_scope BEFORE INSERT OR UPDATE ON events_mentorround FOR EACH ROW EXECUTE FUNCTION events_mentorround_scope_guard();
CREATE FUNCTION events_mentorroundlock_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_mentorround r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NEW.mentor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorroundlock_programme_scope BEFORE INSERT OR UPDATE ON events_mentorroundlock FOR EACH ROW EXECUTE FUNCTION events_mentorroundlock_scope_guard();
CREATE FUNCTION events_mentorroundcheckin_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_mentorround r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  IF NEW.mentor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorroundcheckin_programme_scope BEFORE INSERT OR UPDATE ON events_mentorroundcheckin FOR EACH ROW EXECUTE FUNCTION events_mentorroundcheckin_scope_guard();
CREATE FUNCTION events_mentorconflict_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.mentor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor event mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorconflict_programme_scope BEFORE INSERT OR UPDATE ON events_mentorconflict FOR EACH ROW EXECUTE FUNCTION events_mentorconflict_scope_guard();
CREATE FUNCTION events_mentornomination_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.mentor_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventroleassignment r WHERE r.id=NEW.mentor_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme mentor event mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.round_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_mentorround r WHERE r.id=NEW.round_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme round event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentornomination_programme_scope BEFORE INSERT OR UPDATE ON events_mentornomination FOR EACH ROW EXECUTE FUNCTION events_mentornomination_scope_guard();
CREATE FUNCTION events_mentorimportpreview_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentorimportpreview_programme_scope BEFORE INSERT OR UPDATE ON events_mentorimportpreview FOR EACH ROW EXECUTE FUNCTION events_mentorimportpreview_scope_guard();
CREATE FUNCTION events_mentornotificationintent_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_event WHERE id=owner_event AND makerspace_id=NEW.makerspace_id) THEN RAISE EXCEPTION 'programme host mismatch'; END IF;
  IF NEW.request_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventhelprequest r WHERE r.id=NEW.request_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme request event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_mentornotificationintent_programme_scope BEFORE INSERT OR UPDATE ON events_mentornotificationintent FOR EACH ROW EXECUTE FUNCTION events_mentornotificationintent_scope_guard();
CREATE FUNCTION events_eventmemberpresentation_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventmemberpresentation_programme_scope BEFORE INSERT OR UPDATE ON events_eventmemberpresentation FOR EACH ROW EXECUTE FUNCTION events_eventmemberpresentation_scope_guard();
CREATE FUNCTION events_eventmembercard_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_eventmemberpresentation p2 WHERE p2.id=NEW.presentation_id);
  IF NEW.presentation_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventmemberpresentation r WHERE r.id=NEW.presentation_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme presentation event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventmembercard_programme_scope BEFORE INSERT OR UPDATE ON events_eventmembercard FOR EACH ROW EXECUTE FUNCTION events_eventmembercard_scope_guard();
CREATE FUNCTION events_eventpresentationcommand_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_eventmemberpresentation p2 WHERE p2.id=NEW.presentation_id);
  IF NEW.presentation_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventmemberpresentation r WHERE r.id=NEW.presentation_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme presentation event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventpresentationcommand_programme_scope BEFORE INSERT OR UPDATE ON events_eventpresentationcommand FOR EACH ROW EXECUTE FUNCTION events_eventpresentationcommand_scope_guard();
CREATE FUNCTION events_galleryconsent_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryconsent_programme_scope BEFORE INSERT OR UPDATE ON events_galleryconsent FOR EACH ROW EXECUTE FUNCTION events_galleryconsent_scope_guard();
CREATE FUNCTION events_galleryconsentitem_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_galleryconsent p2 WHERE p2.id=NEW.consent_id);
  IF NEW.consent_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_galleryconsent r WHERE r.id=NEW.consent_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme consent event mismatch'; END IF;
  IF NEW.asset_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionasset r WHERE r.id=NEW.asset_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme asset event mismatch'; END IF;
  IF NEW.link_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionlink r WHERE r.id=NEW.link_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme link event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryconsentitem_programme_scope BEFORE INSERT OR UPDATE ON events_galleryconsentitem FOR EACH ROW EXECUTE FUNCTION events_galleryconsentitem_scope_guard();
CREATE FUNCTION events_galleryconsentrevision_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_galleryconsent p2 WHERE p2.id=NEW.consent_id);
  IF NEW.consent_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_galleryconsent r WHERE r.id=NEW.consent_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme consent event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryconsentrevision_programme_scope BEFORE INSERT OR UPDATE ON events_galleryconsentrevision FOR EACH ROW EXECUTE FUNCTION events_galleryconsentrevision_scope_guard();
CREATE FUNCTION events_gallerypublication_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.result_revision_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.result_revision_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme result_revision event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_gallerypublication_programme_scope BEFORE INSERT OR UPDATE ON events_gallerypublication FOR EACH ROW EXECUTE FUNCTION events_gallerypublication_scope_guard();
CREATE FUNCTION events_galleryentry_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.publication_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_gallerypublication r WHERE r.id=NEW.publication_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme publication event mismatch'; END IF;
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  IF NEW.hidden_reason_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.hidden_reason_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme hidden_reason event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryentry_programme_scope BEFORE INSERT OR UPDATE ON events_galleryentry FOR EACH ROW EXECUTE FUNCTION events_galleryentry_scope_guard();
CREATE FUNCTION events_galleryentryasset_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_galleryentry p2 WHERE p2.id=NEW.entry_id);
  IF NEW.entry_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_galleryentry r WHERE r.id=NEW.entry_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme entry event mismatch'; END IF;
  IF NEW.asset_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionasset r WHERE r.id=NEW.asset_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme asset event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryentryasset_programme_scope BEFORE INSERT OR UPDATE ON events_galleryentryasset FOR EACH ROW EXECUTE FUNCTION events_galleryentryasset_scope_guard();
CREATE FUNCTION events_galleryentrylink_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_galleryentry p2 WHERE p2.id=NEW.entry_id);
  IF NEW.entry_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_galleryentry r WHERE r.id=NEW.entry_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme entry event mismatch'; END IF;
  IF NEW.link_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionlink r WHERE r.id=NEW.link_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme link event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryentrylink_programme_scope BEFORE INSERT OR UPDATE ON events_galleryentrylink FOR EACH ROW EXECUTE FUNCTION events_galleryentrylink_scope_guard();
CREATE FUNCTION events_galleryamendment_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_gallerypublication p2 WHERE p2.id=NEW.publication_id);
  IF NEW.publication_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_gallerypublication r WHERE r.id=NEW.publication_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme publication event mismatch'; END IF;
  IF NEW.entry_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_galleryentry r WHERE r.id=NEW.entry_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme entry event mismatch'; END IF;
  IF NEW.result_revision_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision r WHERE r.id=NEW.result_revision_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme result_revision event mismatch'; END IF;
  IF NEW.reason_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_judgingreason r WHERE r.id=NEW.reason_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme reason event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryamendment_programme_scope BEFORE INSERT OR UPDATE ON events_galleryamendment FOR EACH ROW EXECUTE FUNCTION events_galleryamendment_scope_guard();
CREATE FUNCTION events_submissionasset_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.submission_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonsubmission r WHERE r.id=NEW.submission_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme submission event mismatch'; END IF;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_submissionasset_programme_scope BEFORE INSERT OR UPDATE ON events_submissionasset FOR EACH ROW EXECUTE FUNCTION events_submissionasset_scope_guard();
CREATE FUNCTION events_hackathonparticipantasset_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.member_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.member_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonparticipantasset_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonparticipantasset FOR EACH ROW EXECUTE FUNCTION events_hackathonparticipantasset_scope_guard();
CREATE FUNCTION events_submissionassetwork_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := COALESCE((SELECT p2.event_id FROM events_submissionasset p2 WHERE p2.id=NEW.asset_id), (SELECT event_id FROM events_hackathonparticipantasset WHERE id=NEW.participant_asset_id));
  IF NEW.asset_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionasset r WHERE r.id=NEW.asset_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme asset event mismatch'; END IF;
  IF NEW.participant_asset_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonparticipantasset r WHERE r.id=NEW.participant_asset_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme participant_asset event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_submissionassetwork_programme_scope BEFORE INSERT OR UPDATE ON events_submissionassetwork FOR EACH ROW EXECUTE FUNCTION events_submissionassetwork_scope_guard();
CREATE FUNCTION events_hackathonsubmission_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := NEW.event_id;
  IF NEW.team_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonteam r WHERE r.id=NEW.team_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme team event mismatch'; END IF;
  IF NEW.current_snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.current_snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme current_snapshot event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonsubmission_programme_scope BEFORE INSERT OR UPDATE ON events_hackathonsubmission FOR EACH ROW EXECUTE FUNCTION events_hackathonsubmission_scope_guard();
CREATE FUNCTION events_submissionsnapshot_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=NEW.submission_id);
  IF NEW.submission_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonsubmission r WHERE r.id=NEW.submission_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme submission event mismatch'; END IF;
  IF NEW.amendment_of_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.amendment_of_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme amendment_of event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_submissionsnapshot_programme_scope BEFORE INSERT OR UPDATE ON events_submissionsnapshot FOR EACH ROW EXECUTE FUNCTION events_submissionsnapshot_scope_guard();
CREATE FUNCTION events_submissionlink_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=NEW.submission_id);
  IF NEW.submission_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonsubmission r WHERE r.id=NEW.submission_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme submission event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_submissionlink_programme_scope BEFORE INSERT OR UPDATE ON events_submissionlink FOR EACH ROW EXECUTE FUNCTION events_submissionlink_scope_guard();
CREATE FUNCTION events_snapshotasset_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=p3.submission_id) FROM events_submissionsnapshot p3 WHERE p3.id=NEW.snapshot_id);
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  IF NEW.asset_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionasset r WHERE r.id=NEW.asset_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme asset event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_snapshotasset_programme_scope BEFORE INSERT OR UPDATE ON events_snapshotasset FOR EACH ROW EXECUTE FUNCTION events_snapshotasset_scope_guard();
CREATE FUNCTION events_snapshotlink_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=p3.submission_id) FROM events_submissionsnapshot p3 WHERE p3.id=NEW.snapshot_id);
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  IF NEW.link_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionlink r WHERE r.id=NEW.link_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme link event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_snapshotlink_programme_scope BEFORE INSERT OR UPDATE ON events_snapshotlink FOR EACH ROW EXECUTE FUNCTION events_snapshotlink_scope_guard();
CREATE FUNCTION events_snapshottrack_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=p3.submission_id) FROM events_submissionsnapshot p3 WHERE p3.id=NEW.snapshot_id);
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  IF NEW.track_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathontrack r WHERE r.id=NEW.track_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme track event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_snapshottrack_programme_scope BEFORE INSERT OR UPDATE ON events_snapshottrack FOR EACH ROW EXECUTE FUNCTION events_snapshottrack_scope_guard();
CREATE FUNCTION events_snapshotprize_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=p3.submission_id) FROM events_submissionsnapshot p3 WHERE p3.id=NEW.snapshot_id);
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  IF NEW.prize_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonprize r WHERE r.id=NEW.prize_id AND r.event_id=owner_event) THEN RAISE EXCEPTION 'programme prize event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_snapshotprize_programme_scope BEFORE INSERT OR UPDATE ON events_snapshotprize FOR EACH ROW EXECUTE FUNCTION events_snapshotprize_scope_guard();
CREATE FUNCTION events_submissionintegrityflag_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_event bigint;
BEGIN
  owner_event := (SELECT (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=p3.submission_id) FROM events_submissionsnapshot p3 WHERE p3.id=NEW.snapshot_id);
  IF NEW.snapshot_id IS NOT NULL AND owner_event IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_submissionsnapshot r WHERE r.id=NEW.snapshot_id AND (SELECT p2.event_id FROM events_hackathonsubmission p2 WHERE p2.id=r.submission_id)=owner_event) THEN RAISE EXCEPTION 'programme snapshot event mismatch'; END IF;
  IF NEW.reviewer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM accounts_user WHERE id=NEW.reviewer_id AND account_kind='member') THEN RAISE EXCEPTION 'programme requires member identity'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_submissionintegrityflag_programme_scope BEFORE INSERT OR UPDATE ON events_submissionintegrityflag FOR EACH ROW EXECUTE FUNCTION events_submissionintegrityflag_scope_guard();
CREATE FUNCTION events_hackathoncocrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_hackathoncocrevision_programme_history BEFORE UPDATE OR DELETE ON events_hackathoncocrevision FOR EACH ROW EXECUTE FUNCTION events_hackathoncocrevision_history_guard();
CREATE FUNCTION events_hackathonapplicationanswerrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_hackathonapplicationanswerrevision_programme_history BEFORE UPDATE OR DELETE ON events_hackathonapplicationanswerrevision FOR EACH ROW EXECUTE FUNCTION events_hackathonapplicationanswerrevision_history_guard();
CREATE FUNCTION events_applicationreview_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_applicationreview_programme_history BEFORE UPDATE OR DELETE ON events_applicationreview FOR EACH ROW EXECUTE FUNCTION events_applicationreview_history_guard();
CREATE FUNCTION events_teamcomment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_teamcomment_programme_history BEFORE UPDATE OR DELETE ON events_teamcomment FOR EACH ROW EXECUTE FUNCTION events_teamcomment_history_guard();
CREATE FUNCTION events_hackathonteamexception_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.member_id IS NOT DISTINCT FROM OLD.member_id OR (NEW.member_id IS NULL AND OLD.member_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['member_id']::text[])=(to_jsonb(OLD)-ARRAY['member_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_hackathonteamexception_programme_history BEFORE UPDATE OR DELETE ON events_hackathonteamexception FOR EACH ROW EXECUTE FUNCTION events_hackathonteamexception_history_guard();
CREATE FUNCTION events_eventcontributionhoursentry_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventcontributionhoursentry_programme_history BEFORE UPDATE OR DELETE ON events_eventcontributionhoursentry FOR EACH ROW EXECUTE FUNCTION events_eventcontributionhoursentry_history_guard();
CREATE FUNCTION events_eventshiftattendancecorrection_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventshiftattendancecorrection_programme_history BEFORE UPDATE OR DELETE ON events_eventshiftattendancecorrection FOR EACH ROW EXECUTE FUNCTION events_eventshiftattendancecorrection_history_guard();
CREATE FUNCTION events_eventhelpaction_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventhelpaction_programme_history BEFORE UPDATE OR DELETE ON events_eventhelpaction FOR EACH ROW EXECUTE FUNCTION events_eventhelpaction_history_guard();
CREATE FUNCTION events_eventhelpcomment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.author_id IS NOT DISTINCT FROM OLD.author_id OR (NEW.author_id IS NULL AND OLD.author_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['author_id']::text[])=(to_jsonb(OLD)-ARRAY['author_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventhelpcomment_programme_history BEFORE UPDATE OR DELETE ON events_eventhelpcomment FOR EACH ROW EXECUTE FUNCTION events_eventhelpcomment_history_guard();
CREATE FUNCTION events_mentorroundcheckin_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_mentorroundcheckin_programme_history BEFORE UPDATE OR DELETE ON events_mentorroundcheckin FOR EACH ROW EXECUTE FUNCTION events_mentorroundcheckin_history_guard();
CREATE FUNCTION events_mentornomination_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_mentornomination_programme_history BEFORE UPDATE OR DELETE ON events_mentornomination FOR EACH ROW EXECUTE FUNCTION events_mentornomination_history_guard();
CREATE FUNCTION events_officehourschange_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_officehourschange_programme_history BEFORE UPDATE OR DELETE ON events_officehourschange FOR EACH ROW EXECUTE FUNCTION events_officehourschange_history_guard();
CREATE FUNCTION events_eventroleanswerrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventroleanswerrevision_programme_history BEFORE UPDATE OR DELETE ON events_eventroleanswerrevision FOR EACH ROW EXECUTE FUNCTION events_eventroleanswerrevision_history_guard();
CREATE FUNCTION events_eventrequirementoverride_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventrequirementoverride_programme_history BEFORE UPDATE OR DELETE ON events_eventrequirementoverride FOR EACH ROW EXECUTE FUNCTION events_eventrequirementoverride_history_guard();
CREATE FUNCTION events_eventcontributoradmission_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventcontributoradmission_programme_history BEFORE UPDATE OR DELETE ON events_eventcontributoradmission FOR EACH ROW EXECUTE FUNCTION events_eventcontributoradmission_history_guard();
CREATE FUNCTION events_mentorassignmentrun_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.created_by_id IS NOT DISTINCT FROM OLD.created_by_id OR (NEW.created_by_id IS NULL AND OLD.created_by_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['created_by_id']::text[])=(to_jsonb(OLD)-ARRAY['created_by_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_mentorassignmentrun_programme_history BEFORE UPDATE OR DELETE ON events_mentorassignmentrun FOR EACH ROW EXECUTE FUNCTION events_mentorassignmentrun_history_guard();
CREATE FUNCTION events_judgingreason_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_judgingreason_programme_history BEFORE UPDATE OR DELETE ON events_judgingreason FOR EACH ROW EXECUTE FUNCTION events_judgingreason_history_guard();
CREATE FUNCTION events_judgerankingchoice_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_judgerankingchoice_programme_history BEFORE UPDATE OR DELETE ON events_judgerankingchoice FOR EACH ROW EXECUTE FUNCTION events_judgerankingchoice_history_guard();
CREATE FUNCTION events_eventresultrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.created_by_id IS NOT DISTINCT FROM OLD.created_by_id OR (NEW.created_by_id IS NULL AND OLD.created_by_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['created_by_id']::text[])=(to_jsonb(OLD)-ARRAY['created_by_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventresultrevision_programme_history BEFORE UPDATE OR DELETE ON events_eventresultrevision FOR EACH ROW EXECUTE FUNCTION events_eventresultrevision_history_guard();
CREATE FUNCTION events_eventresultround_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventresultround_programme_history BEFORE UPDATE OR DELETE ON events_eventresultround FOR EACH ROW EXECUTE FUNCTION events_eventresultround_history_guard();
CREATE FUNCTION events_eventaward_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventaward_programme_history BEFORE UPDATE OR DELETE ON events_eventaward FOR EACH ROW EXECUTE FUNCTION events_eventaward_history_guard();
CREATE FUNCTION events_resultannouncement_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.published_by_id IS NOT DISTINCT FROM OLD.published_by_id OR (NEW.published_by_id IS NULL AND OLD.published_by_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['published_by_id']::text[])=(to_jsonb(OLD)-ARRAY['published_by_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_resultannouncement_programme_history BEFORE UPDATE OR DELETE ON events_resultannouncement FOR EACH ROW EXECUTE FUNCTION events_resultannouncement_history_guard();
CREATE FUNCTION events_sponsorwinnerproposal_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.proposed_by_id IS NOT DISTINCT FROM OLD.proposed_by_id OR (NEW.proposed_by_id IS NULL AND OLD.proposed_by_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['proposed_by_id']::text[])=(to_jsonb(OLD)-ARRAY['proposed_by_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_sponsorwinnerproposal_programme_history BEFORE UPDATE OR DELETE ON events_sponsorwinnerproposal FOR EACH ROW EXECUTE FUNCTION events_sponsorwinnerproposal_history_guard();
CREATE FUNCTION events_sponsorresumeconsenthistory_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_sponsorresumeconsenthistory_programme_history BEFORE UPDATE OR DELETE ON events_sponsorresumeconsenthistory FOR EACH ROW EXECUTE FUNCTION events_sponsorresumeconsenthistory_history_guard();
CREATE FUNCTION events_galleryconsentrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_galleryconsentrevision_programme_history BEFORE UPDATE OR DELETE ON events_galleryconsentrevision FOR EACH ROW EXECUTE FUNCTION events_galleryconsentrevision_history_guard();
CREATE FUNCTION events_galleryamendment_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_galleryamendment_programme_history BEFORE UPDATE OR DELETE ON events_galleryamendment FOR EACH ROW EXECUTE FUNCTION events_galleryamendment_history_guard();
CREATE FUNCTION events_eventformrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.created_by_id IS NOT DISTINCT FROM OLD.created_by_id OR (NEW.created_by_id IS NULL AND OLD.created_by_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['created_by_id']::text[])=(to_jsonb(OLD)-ARRAY['created_by_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventformrevision_programme_history BEFORE UPDATE OR DELETE ON events_eventformrevision FOR EACH ROW EXECUTE FUNCTION events_eventformrevision_history_guard();
CREATE FUNCTION events_eventbroadcastpreview_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.created_by_id IS NOT DISTINCT FROM OLD.created_by_id OR (NEW.created_by_id IS NULL AND OLD.created_by_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['created_by_id']::text[])=(to_jsonb(OLD)-ARRAY['created_by_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventbroadcastpreview_programme_history BEFORE UPDATE OR DELETE ON events_eventbroadcastpreview FOR EACH ROW EXECUTE FUNCTION events_eventbroadcastpreview_history_guard();
CREATE FUNCTION events_eventcertificatelibraryrevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventcertificatelibraryrevision_programme_history BEFORE UPDATE OR DELETE ON events_eventcertificatelibraryrevision FOR EACH ROW EXECUTE FUNCTION events_eventcertificatelibraryrevision_history_guard();
CREATE FUNCTION events_eventbadgetemplaterevision_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventbadgetemplaterevision_programme_history BEFORE UPDATE OR DELETE ON events_eventbadgetemplaterevision FOR EACH ROW EXECUTE FUNCTION events_eventbadgetemplaterevision_history_guard();
CREATE FUNCTION events_eventcredentialcommand_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  IF TG_OP='UPDATE' AND (NEW.actor_id IS NOT DISTINCT FROM OLD.actor_id OR (NEW.actor_id IS NULL AND OLD.actor_id IS NOT NULL)) AND (to_jsonb(NEW)-ARRAY['actor_id']::text[])=(to_jsonb(OLD)-ARRAY['actor_id']::text[]) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventcredentialcommand_programme_history BEFORE UPDATE OR DELETE ON events_eventcredentialcommand FOR EACH ROW EXECUTE FUNCTION events_eventcredentialcommand_history_guard();
CREATE FUNCTION events_eventpresentationcommand_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_eventpresentationcommand_programme_history BEFORE UPDATE OR DELETE ON events_eventpresentationcommand FOR EACH ROW EXECUTE FUNCTION events_eventpresentationcommand_history_guard();
CREATE FUNCTION events_judgerankingballot_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_judgerankingballot_programme_history BEFORE UPDATE OR DELETE ON events_judgerankingballot FOR EACH ROW EXECUTE FUNCTION events_judgerankingballot_history_guard();
CREATE FUNCTION events_galleryentryasset_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_galleryentryasset_programme_history BEFORE UPDATE OR DELETE ON events_galleryentryasset FOR EACH ROW EXECUTE FUNCTION events_galleryentryasset_history_guard();
CREATE FUNCTION events_galleryentrylink_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  
  RAISE EXCEPTION 'programme history is append-only';
END;
$$;
CREATE TRIGGER events_galleryentrylink_programme_history BEFORE UPDATE OR DELETE ON events_galleryentrylink FOR EACH ROW EXECUTE FUNCTION events_galleryentrylink_history_guard();

CREATE OR REPLACE FUNCTION events_submission_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('app.allow_immutable_delete', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'submission snapshot is immutable';
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION events_submission_asset_guard() RETURNS trigger AS $$
DECLARE owner_event bigint; owner_team bigint;
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF current_setting('app.allow_immutable_delete', true) = 'on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'submission asset metadata is retained';
  END IF;
  IF TG_TABLE_NAME = 'events_submissionasset' THEN
    SELECT event_id, team_id INTO owner_event, owner_team
      FROM events_hackathonsubmission WHERE id = NEW.submission_id;
    IF owner_event IS DISTINCT FROM NEW.event_id OR owner_team IS DISTINCT FROM NEW.team_id THEN
      RAISE EXCEPTION 'submission asset owner mismatch';
    END IF;
  END IF;
  IF TG_OP = 'UPDATE' AND (OLD.ready_at IS NOT NULL OR OLD.sha256 <> '') AND
    (NEW.sha256, NEW.original_sha256, NEW.actual_bytes, NEW.canonical_mime, NEW.object_key,
     NEW.final_version_id, NEW.event_id, NEW.public_id, NEW.generation)
    IS DISTINCT FROM
    (OLD.sha256, OLD.original_sha256, OLD.actual_bytes, OLD.canonical_mime, OLD.object_key,
     OLD.final_version_id, OLD.event_id, OLD.public_id, OLD.generation) THEN
    RAISE EXCEPTION 'ready submission asset content is immutable';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.expired_at IS NOT NULL AND NEW.expired_at IS NULL THEN
    RAISE EXCEPTION 'expired submission asset cannot revive';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION events_snapshot_reference_guard() RETURNS trigger AS $$
DECLARE owning_submission bigint; owning_event bigint; owning_team bigint; valid boolean;
BEGIN
  SELECT s.id, s.event_id, s.team_id INTO owning_submission, owning_event, owning_team
    FROM events_submissionsnapshot snap JOIN events_hackathonsubmission s ON s.id=snap.submission_id
    WHERE snap.id=NEW.snapshot_id;
  IF TG_TABLE_NAME='events_snapshotasset' THEN
    SELECT (submission_id=owning_submission AND event_id=owning_event AND team_id=owning_team
      AND state='ready' AND scan_status IN ('clean','skipped') AND expired_at IS NULL
      AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)) INTO valid
      FROM events_submissionasset WHERE id=NEW.asset_id;
  ELSIF TG_TABLE_NAME='events_snapshotlink' THEN
    SELECT submission_id=owning_submission INTO valid FROM events_submissionlink WHERE id=NEW.link_id;
  ELSIF TG_TABLE_NAME='events_snapshottrack' THEN
    SELECT event_id=owning_event INTO valid FROM events_hackathontrack WHERE id=NEW.track_id;
  ELSIF TG_TABLE_NAME='events_snapshotprize' THEN
    SELECT event_id=owning_event INTO valid FROM events_hackathonprize WHERE id=NEW.prize_id;
  END IF;
  IF valid IS DISTINCT FROM TRUE THEN RAISE EXCEPTION 'snapshot reference owner mismatch'; END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION events_submission_project_guard() RETURNS trigger AS $$
DECLARE owning_event bigint; owning_submission bigint;
BEGIN
  SELECT event_id INTO owning_event FROM events_hackathonteam WHERE id=NEW.team_id;
  IF owning_event IS DISTINCT FROM NEW.event_id THEN
    RAISE EXCEPTION 'submission team event mismatch';
  END IF;
  IF NEW.current_snapshot_id IS NOT NULL THEN
    SELECT submission_id INTO owning_submission FROM events_submissionsnapshot WHERE id=NEW.current_snapshot_id;
    IF owning_submission IS DISTINCT FROM NEW.id THEN
      RAISE EXCEPTION 'submission current snapshot mismatch';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_hackathonsubmission_owner BEFORE INSERT OR UPDATE ON events_hackathonsubmission FOR EACH ROW EXECUTE FUNCTION events_submission_project_guard();
CREATE TRIGGER events_submissionsnapshot_immutable BEFORE UPDATE OR DELETE ON events_submissionsnapshot FOR EACH ROW EXECUTE FUNCTION events_submission_immutable();
CREATE TRIGGER events_snapshotasset_immutable BEFORE UPDATE OR DELETE ON events_snapshotasset FOR EACH ROW EXECUTE FUNCTION events_submission_immutable();
CREATE TRIGGER events_snapshotlink_immutable BEFORE UPDATE OR DELETE ON events_snapshotlink FOR EACH ROW EXECUTE FUNCTION events_submission_immutable();
CREATE TRIGGER events_snapshottrack_immutable BEFORE UPDATE OR DELETE ON events_snapshottrack FOR EACH ROW EXECUTE FUNCTION events_submission_immutable();
CREATE TRIGGER events_snapshotprize_immutable BEFORE UPDATE OR DELETE ON events_snapshotprize FOR EACH ROW EXECUTE FUNCTION events_submission_immutable();
CREATE TRIGGER events_submissionasset_guard BEFORE INSERT OR UPDATE OR DELETE ON events_submissionasset FOR EACH ROW EXECUTE FUNCTION events_submission_asset_guard();
CREATE TRIGGER events_hackathonparticipantasset_guard BEFORE INSERT OR UPDATE OR DELETE ON events_hackathonparticipantasset FOR EACH ROW EXECUTE FUNCTION events_submission_asset_guard();
CREATE TRIGGER events_snapshotasset_owner BEFORE INSERT ON events_snapshotasset FOR EACH ROW EXECUTE FUNCTION events_snapshot_reference_guard();
CREATE TRIGGER events_snapshotlink_owner BEFORE INSERT ON events_snapshotlink FOR EACH ROW EXECUTE FUNCTION events_snapshot_reference_guard();
CREATE TRIGGER events_snapshottrack_owner BEFORE INSERT ON events_snapshottrack FOR EACH ROW EXECUTE FUNCTION events_snapshot_reference_guard();
CREATE TRIGGER events_snapshotprize_owner BEFORE INSERT ON events_snapshotprize FOR EACH ROW EXECUTE FUNCTION events_snapshot_reference_guard();
CREATE FUNCTION events_programme_certificate_subject_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE subject_event bigint; subject_member bigint;
BEGIN
  IF TG_OP='UPDATE' AND (NEW.event_id,NEW.registration_id,NEW.role_assignment_id,NEW.kind,NEW.award_id,NEW.result_revision_id,NEW.serial)
    IS DISTINCT FROM (OLD.event_id,OLD.registration_id,OLD.role_assignment_id,OLD.kind,OLD.award_id,OLD.result_revision_id,OLD.serial)
    THEN RAISE EXCEPTION 'certificate subjects are immutable'; END IF;
  IF NEW.registration_id IS NOT NULL THEN
    SELECT event_id,member_id INTO subject_event,subject_member FROM events_eventregistration WHERE id=NEW.registration_id;
    IF NEW.response_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventfeedbackresponse WHERE id=NEW.response_id AND registration_id=NEW.registration_id)
      THEN RAISE EXCEPTION 'certificate response subject mismatch'; END IF;
  ELSE
    SELECT event_id,member_id INTO subject_event,subject_member FROM events_eventroleassignment WHERE id=NEW.role_assignment_id;
  END IF;
  IF subject_event IS DISTINCT FROM NEW.event_id OR (NEW.recipient_member_id IS NOT NULL AND NEW.recipient_member_id IS DISTINCT FROM subject_member)
    THEN RAISE EXCEPTION 'certificate subject event/member mismatch'; END IF;
  IF NEW.award_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_hackathonprize WHERE id=NEW.award_id AND event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'certificate award event mismatch'; END IF;
  IF NEW.result_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventresultrevision WHERE id=NEW.result_revision_id AND event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'certificate result event mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventattendancecertificate_programme_subject BEFORE INSERT OR UPDATE ON events_eventattendancecertificate FOR EACH ROW EXECUTE FUNCTION events_programme_certificate_subject_guard();
CREATE FUNCTION events_programme_resume_consent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_hackathonparticipantasset a WHERE a.id=NEW.participant_asset_id
    AND a.event_id=NEW.event_id AND a.member_id=NEW.member_id AND a.sha256=NEW.asset_sha256 AND a.purpose='resume')
    THEN RAISE EXCEPTION 'resume consent owner/content mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_participantsponsorresumeconsent_programme_asset BEFORE INSERT OR UPDATE ON events_participantsponsorresumeconsent FOR EACH ROW EXECUTE FUNCTION events_programme_resume_consent_guard();
CREATE FUNCTION events_programme_presentation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.selected_profile_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM makerspaces_memberprofile p JOIN makerspaces_makerspacemembership m ON m.id=p.membership_id
    WHERE p.id=NEW.selected_profile_id AND m.id=NEW.selected_membership_id AND m.user_id=NEW.member_id)
    THEN RAISE EXCEPTION 'presentation source owner mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventmemberpresentation_programme_source BEFORE INSERT OR UPDATE ON events_eventmemberpresentation FOR EACH ROW EXECUTE FUNCTION events_programme_presentation_guard();
CREATE FUNCTION events_programme_application_member_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.registration_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventregistration
    WHERE id=NEW.registration_id AND member_id=NEW.member_id AND event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'application registration identity mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonapplication_programme_member BEFORE INSERT OR UPDATE ON events_hackathonapplication FOR EACH ROW EXECUTE FUNCTION events_programme_application_member_guard();
CREATE FUNCTION events_programme_team_member_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_hackathonapplication WHERE id=NEW.application_id
    AND event_id=NEW.event_id AND member_id=NEW.member_id)
    THEN RAISE EXCEPTION 'team application identity mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_hackathonteammember_programme_member BEFORE INSERT OR UPDATE ON events_hackathonteammember FOR EACH ROW EXECUTE FUNCTION events_programme_team_member_guard();
CREATE FUNCTION events_programme_team_leader_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE team_id bigint;
BEGIN
  IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN NULL; END IF;
  IF TG_TABLE_NAME='events_hackathonteam' THEN team_id:=NEW.id;
  ELSIF TG_OP='DELETE' THEN team_id:=OLD.team_id; ELSE team_id:=NEW.team_id; END IF;
  IF EXISTS (SELECT 1 FROM events_hackathonteam t WHERE t.id=team_id AND t.state<>'disbanded'
    AND NOT EXISTS (SELECT 1 FROM events_hackathonteammember m WHERE m.team_id=t.id AND m.member_id=t.leader_id AND m.state='active'))
    THEN RAISE EXCEPTION 'active team leader must belong to the team'; END IF;
  RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER events_hackathonteam_deferred_leader AFTER INSERT OR UPDATE ON events_hackathonteam DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION events_programme_team_leader_guard();
CREATE CONSTRAINT TRIGGER events_hackathonteammember_deferred_leader AFTER INSERT OR UPDATE OR DELETE ON events_hackathonteammember DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION events_programme_team_leader_guard();
CREATE FUNCTION events_programme_credential_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'credential history is retained';
  END IF;
  IF NEW.revoked_by_id IS NULL AND OLD.revoked_by_id IS NOT NULL AND (to_jsonb(NEW)-'revoked_by_id')=(to_jsonb(OLD)-'revoked_by_id') THEN RETURN NEW; END IF;
  IF (to_jsonb(NEW)-ARRAY['revoked_at','revoked_by_id','revocation_reason'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['revoked_at','revoked_by_id','revocation_reason'])
    OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
    THEN RAISE EXCEPTION 'credential generations permit one revocation only'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventregistrationcredential_programme_generation BEFORE UPDATE OR DELETE ON events_eventregistrationcredential FOR EACH ROW EXECUTE FUNCTION events_programme_credential_guard();
CREATE OR REPLACE FUNCTION events_template_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='events_eventcertificatetemplaterevision' THEN
    IF NEW.artwork_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventcertificateartwork a
      WHERE a.id=NEW.artwork_id AND a.event_id=NEW.event_id AND a.promoted_at IS NOT NULL)
      THEN RAISE EXCEPTION 'invalid certificate artwork ownership'; END IF;
  ELSE
    IF NEW.template_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventcertificatetemplaterevision t
      WHERE t.id=NEW.template_revision_id AND t.event_id=NEW.event_id)
      THEN RAISE EXCEPTION 'invalid certificate template ownership'; END IF;
  END IF;
  RETURN NEW;
END; $$;
CREATE FUNCTION events_applicationreview_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=(SELECT p2.event_id FROM events_applicationreviewassignment p2 WHERE p2.id=NEW.assignment_id); PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_applicationreview_programme_pii_fence BEFORE INSERT OR UPDATE ON events_applicationreview FOR EACH ROW EXECUTE FUNCTION events_applicationreview_pii_fence_guard();
CREATE FUNCTION events_eventanswerderivation_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventanswerderivation_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventanswerderivation FOR EACH ROW EXECUTE FUNCTION events_eventanswerderivation_pii_fence_guard();
CREATE FUNCTION events_eventattendancecertificate_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventattendancecertificate_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventattendancecertificate FOR EACH ROW EXECUTE FUNCTION events_eventattendancecertificate_pii_fence_guard();
CREATE FUNCTION events_eventcontributionhoursentry_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventcontributionhoursentry_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventcontributionhoursentry FOR EACH ROW EXECUTE FUNCTION events_eventcontributionhoursentry_pii_fence_guard();
CREATE FUNCTION events_eventhelpaction_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventhelpaction_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventhelpaction FOR EACH ROW EXECUTE FUNCTION events_eventhelpaction_pii_fence_guard();
CREATE FUNCTION events_eventhelpcomment_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventhelpcomment_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventhelpcomment FOR EACH ROW EXECUTE FUNCTION events_eventhelpcomment_pii_fence_guard();
CREATE FUNCTION events_eventhelprequest_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventhelprequest_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventhelprequest FOR EACH ROW EXECUTE FUNCTION events_eventhelprequest_pii_fence_guard();
CREATE FUNCTION events_eventrequirementoverride_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventrequirementoverride_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventrequirementoverride FOR EACH ROW EXECUTE FUNCTION events_eventrequirementoverride_pii_fence_guard();
CREATE FUNCTION events_eventroleanswerrevision_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventroleanswerrevision_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventroleanswerrevision FOR EACH ROW EXECUTE FUNCTION events_eventroleanswerrevision_pii_fence_guard();
CREATE FUNCTION events_eventroleassignment_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventroleassignment_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventroleassignment FOR EACH ROW EXECUTE FUNCTION events_eventroleassignment_pii_fence_guard();
CREATE FUNCTION events_eventshiftattendancecorrection_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_eventshiftattendancecorrection_programme_pii_fence BEFORE INSERT OR UPDATE ON events_eventshiftattendancecorrection FOR EACH ROW EXECUTE FUNCTION events_eventshiftattendancecorrection_pii_fence_guard();
CREATE FUNCTION events_hackathonapplication_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_hackathonapplication_programme_pii_fence BEFORE INSERT OR UPDATE ON events_hackathonapplication FOR EACH ROW EXECUTE FUNCTION events_hackathonapplication_pii_fence_guard();
CREATE FUNCTION events_hackathonapplicationanswerrevision_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=(SELECT p2.event_id FROM events_hackathonapplication p2 WHERE p2.id=NEW.application_id); PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_hackathonapplicationanswerrevision_programme_pii_fence BEFORE INSERT OR UPDATE ON events_hackathonapplicationanswerrevision FOR EACH ROW EXECUTE FUNCTION events_hackathonapplicationanswerrevision_pii_fence_guard();
CREATE FUNCTION events_judgescore_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_judgescore_programme_pii_fence BEFORE INSERT OR UPDATE ON events_judgescore FOR EACH ROW EXECUTE FUNCTION events_judgescore_pii_fence_guard();
CREATE FUNCTION events_judgingreason_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_judgingreason_programme_pii_fence BEFORE INSERT OR UPDATE ON events_judgingreason FOR EACH ROW EXECUTE FUNCTION events_judgingreason_pii_fence_guard();
CREATE FUNCTION events_mentorconflict_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_mentorconflict_programme_pii_fence BEFORE INSERT OR UPDATE ON events_mentorconflict FOR EACH ROW EXECUTE FUNCTION events_mentorconflict_pii_fence_guard();
CREATE FUNCTION events_mentorimportpreview_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_mentorimportpreview_programme_pii_fence BEFORE INSERT OR UPDATE ON events_mentorimportpreview FOR EACH ROW EXECUTE FUNCTION events_mentorimportpreview_pii_fence_guard();
CREATE FUNCTION events_mentorprofile_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_mentorprofile_programme_pii_fence BEFORE INSERT OR UPDATE ON events_mentorprofile FOR EACH ROW EXECUTE FUNCTION events_mentorprofile_pii_fence_guard();
CREATE FUNCTION events_mentorroundcheckin_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_mentorroundcheckin_programme_pii_fence BEFORE INSERT OR UPDATE ON events_mentorroundcheckin FOR EACH ROW EXECUTE FUNCTION events_mentorroundcheckin_pii_fence_guard();
CREATE FUNCTION events_mentorroundlock_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_mentorroundlock_programme_pii_fence BEFORE INSERT OR UPDATE ON events_mentorroundlock FOR EACH ROW EXECUTE FUNCTION events_mentorroundlock_pii_fence_guard();
CREATE FUNCTION events_officehourschange_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=NEW.event_id; PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_officehourschange_programme_pii_fence BEFORE INSERT OR UPDATE ON events_officehourschange FOR EACH ROW EXECUTE FUNCTION events_officehourschange_pii_fence_guard();
CREATE FUNCTION events_teamcomment_pii_fence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE host bigint; BEGIN SELECT makerspace_id INTO host FROM events_event WHERE id=(SELECT p2.event_id FROM events_hackathonteam p2 WHERE p2.id=NEW.team_id); PERFORM pii_assert_mapped_write_allowed(host); RETURN NEW; END;
$$;
CREATE TRIGGER events_teamcomment_programme_pii_fence BEFORE INSERT OR UPDATE ON events_teamcomment FOR EACH ROW EXECUTE FUNCTION events_teamcomment_pii_fence_guard();
CREATE FUNCTION events_programme_receipt_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'command receipts are retained';
  END IF;
  IF (to_jsonb(NEW)-'response_reference') IS DISTINCT FROM (to_jsonb(OLD)-'response_reference')
     OR OLD.response_reference IS NOT NULL OR NEW.response_reference IS NULL
     OR jsonb_typeof(NEW.response_reference)<>'object' THEN
    RAISE EXCEPTION 'command receipt permits one completion only';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcommandreceipt_programme_completion BEFORE UPDATE OR DELETE ON events_eventcommandreceipt FOR EACH ROW EXECUTE FUNCTION events_programme_receipt_guard();
CREATE FUNCTION events_programme_round_freeze() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state<>'draft' AND (to_jsonb(NEW)-ARRAY['state','version','coverage_exception_id'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','version','coverage_exception_id']) THEN
    RAISE EXCEPTION 'opened round configuration is frozen';
  END IF;
  IF OLD.state<>'draft' AND NEW.state='draft' THEN RAISE EXCEPTION 'round cannot reopen as draft'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judginground_programme_freeze BEFORE UPDATE ON events_judginground FOR EACH ROW EXECUTE FUNCTION events_programme_round_freeze();
CREATE FUNCTION events_programme_criterion_freeze() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE round_key bigint; round_state text; restoring boolean;
BEGIN
  round_key := CASE WHEN TG_OP='DELETE' THEN OLD.round_id ELSE NEW.round_id END;
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
  SELECT r.state, m.lifecycle_state='importing' INTO round_state,restoring
    FROM events_judginground r JOIN events_event e ON e.id=r.event_id
    JOIN makerspaces_makerspace m ON m.id=e.makerspace_id WHERE r.id=round_key FOR UPDATE OF r;
  IF TG_OP='UPDATE' AND NEW.round_id IS DISTINCT FROM OLD.round_id THEN RAISE EXCEPTION 'criterion round is immutable'; END IF;
  IF round_state<>'draft' AND NOT (TG_OP='INSERT' AND restoring) THEN RAISE EXCEPTION 'opened rubric is frozen'; END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgingcriterion_programme_freeze BEFORE INSERT OR UPDATE OR DELETE ON events_judgingcriterion FOR EACH ROW EXECUTE FUNCTION events_programme_criterion_freeze();
CREATE FUNCTION events_programme_score_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE configuration jsonb; mode text;
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'judgment evidence is retained';
  END IF;
  IF TG_OP='UPDATE' AND OLD.submitted_at IS NOT NULL THEN RAISE EXCEPTION 'submitted judgment is immutable'; END IF;
  SELECT r.configuration,r.mode INTO configuration,mode FROM events_judgeassignment a
    JOIN events_judginground r ON r.id=a.round_id WHERE a.id=NEW.assignment_id;
  IF jsonb_typeof(NEW.criterion_values)<>'object' THEN RAISE EXCEPTION 'invalid score shape'; END IF;
  IF NEW.submitted_at IS NOT NULL THEN
    IF mode IS DISTINCT FROM 'weighted_1_5' OR jsonb_typeof(configuration->'criteria') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'submitted score requires frozen weighted rubric'; END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each(NEW.criterion_values) v
      WHERE jsonb_typeof(v.value)<>'number' OR v.value::text !~ '^[1-5]$')
      OR EXISTS (SELECT jsonb_object_keys(NEW.criterion_values) EXCEPT SELECT c->>'key' FROM jsonb_array_elements(configuration->'criteria') c)
      OR EXISTS (SELECT c->>'key' FROM jsonb_array_elements(configuration->'criteria') c EXCEPT SELECT jsonb_object_keys(NEW.criterion_values))
      THEN RAISE EXCEPTION 'submitted scores require every frozen key and integer 1..5'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgescore_programme_submitted BEFORE INSERT OR UPDATE OR DELETE ON events_judgescore FOR EACH ROW EXECUTE FUNCTION events_programme_score_guard();
CREATE FUNCTION events_programme_rank_choice_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ballot events_judgerankingballot%ROWTYPE; assignment events_judgeassignment%ROWTYPE; round_state text; restoring boolean;
BEGIN
  SELECT * INTO ballot FROM events_judgerankingballot WHERE id=NEW.ballot_id;
  SELECT * INTO assignment FROM events_judgeassignment WHERE id=NEW.assignment_id;
  IF (assignment.round_id,assignment.judge_role_assignment_id,assignment.batch)
    IS DISTINCT FROM (ballot.round_id,ballot.judge_id,ballot.batch) THEN RAISE EXCEPTION 'ballot assignment mismatch'; END IF;
  SELECT r.state,m.lifecycle_state='importing' INTO round_state,restoring FROM events_judginground r
    JOIN events_event e ON e.id=r.event_id JOIN makerspaces_makerspace m ON m.id=e.makerspace_id
    WHERE r.id=ballot.round_id;
  IF round_state<>'open' AND NOT restoring THEN RAISE EXCEPTION 'ranking round is not open'; END IF;
  IF EXISTS (SELECT 1 FROM events_judgerankingchoice c JOIN events_judgeassignment a ON a.id=c.assignment_id
      WHERE c.ballot_id=NEW.ballot_id AND a.submission_snapshot_id=assignment.submission_snapshot_id)
    THEN RAISE EXCEPTION 'ballot repeats snapshot'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_judgerankingchoice_programme_ballot BEFORE INSERT ON events_judgerankingchoice FOR EACH ROW EXECUTE FUNCTION events_programme_rank_choice_guard();
CREATE FUNCTION events_programme_gallery_item_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pinned_snapshot bigint; owner_team bigint;
BEGIN
  SELECT c.snapshot_id,c.team_id INTO pinned_snapshot,owner_team FROM events_galleryconsent c WHERE c.id=NEW.consent_id;
  IF NEW.asset_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_snapshotasset s
    JOIN events_submissionasset a ON a.id=s.asset_id WHERE s.snapshot_id=pinned_snapshot AND a.id=NEW.asset_id AND a.team_id=owner_team)
    THEN RAISE EXCEPTION 'gallery asset not in pinned snapshot/team'; END IF;
  IF NEW.link_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_snapshotlink s
    JOIN events_submissionlink l ON l.id=s.link_id JOIN events_hackathonsubmission p ON p.id=l.submission_id
    WHERE s.snapshot_id=pinned_snapshot AND l.id=NEW.link_id AND p.team_id=owner_team)
    THEN RAISE EXCEPTION 'gallery link not in pinned snapshot/team'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryconsentitem_programme_selection BEFORE INSERT OR UPDATE ON events_galleryconsentitem FOR EACH ROW EXECUTE FUNCTION events_programme_gallery_item_guard();
CREATE FUNCTION events_programme_gallery_entry_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-ARRAY['version','hidden_at','hidden_reason_id'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['version','hidden_at','hidden_reason_id'])
    THEN RAISE EXCEPTION 'gallery publication selection is frozen'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryentry_programme_selection BEFORE UPDATE ON events_galleryentry FOR EACH ROW EXECUTE FUNCTION events_programme_gallery_entry_guard();
CREATE FUNCTION events_programme_gallery_consent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM events_submissionsnapshot s JOIN events_hackathonsubmission p ON p.id=s.submission_id
    WHERE s.id=NEW.snapshot_id AND p.team_id=NEW.team_id AND p.event_id=NEW.event_id)
    THEN RAISE EXCEPTION 'gallery snapshot team mismatch'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryconsent_programme_snapshot BEFORE INSERT OR UPDATE ON events_galleryconsent FOR EACH ROW EXECUTE FUNCTION events_programme_gallery_consent_guard();
CREATE FUNCTION events_programme_gallery_reference_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pinned_snapshot bigint;
BEGIN
  SELECT snapshot_id INTO pinned_snapshot FROM events_galleryentry WHERE id=NEW.entry_id;
  IF TG_TABLE_NAME='events_galleryentryasset' THEN
    IF NOT EXISTS (SELECT 1 FROM events_snapshotasset WHERE snapshot_id=pinned_snapshot AND asset_id=NEW.asset_id)
      THEN RAISE EXCEPTION 'gallery entry asset mismatch'; END IF;
  ELSE
    IF NOT EXISTS (SELECT 1 FROM events_snapshotlink WHERE snapshot_id=pinned_snapshot AND link_id=NEW.link_id
      AND url=NEW.url AND kind=NEW.kind) THEN RAISE EXCEPTION 'gallery entry frozen link mismatch'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_galleryentryasset_programme_snapshot BEFORE INSERT ON events_galleryentryasset FOR EACH ROW EXECUTE FUNCTION events_programme_gallery_reference_guard();
CREATE TRIGGER events_galleryentrylink_programme_snapshot BEFORE INSERT ON events_galleryentrylink FOR EACH ROW EXECUTE FUNCTION events_programme_gallery_reference_guard();
CREATE FUNCTION events_programme_library_command_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.makerspace_id,NEW.template_id,NEW.operation_id,NEW.request_sha256)
    IS DISTINCT FROM (OLD.makerspace_id,OLD.template_id,OLD.operation_id,OLD.request_sha256)
    OR OLD.result->>'phase'='applied' THEN RAISE EXCEPTION 'applied library receipt is immutable'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcertificatelibrarycommand_programme_completion BEFORE UPDATE ON events_eventcertificatelibrarycommand FOR EACH ROW EXECUTE FUNCTION events_programme_library_command_guard();
CREATE FUNCTION events_programme_promoted_library_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    IF OLD.promoted_at IS NULL OR current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'promoted library artwork is retained';
  END IF;
  IF OLD.promoted_at IS NOT NULL AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)
    THEN RAISE EXCEPTION 'promoted library artwork is immutable'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventcertificatelibraryartwork_programme_promoted BEFORE UPDATE OR DELETE ON events_eventcertificatelibraryartwork FOR EACH ROW EXECUTE FUNCTION events_programme_promoted_library_guard();
CREATE FUNCTION events_programme_print_resource_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'print resource cleanup retains its locator';
  END IF;
  IF OLD.bound_at IS NOT NULL AND (to_jsonb(NEW)-'cleaned_at') IS DISTINCT FROM (to_jsonb(OLD)-'cleaned_at')
    THEN RAISE EXCEPTION 'bound print resource is immutable'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_badgeprintresource_programme_bound BEFORE UPDATE OR DELETE ON events_badgeprintresource FOR EACH ROW EXECUTE FUNCTION events_programme_print_resource_guard();
CREATE FUNCTION events_programme_sent_decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    IF current_setting('app.allow_immutable_delete',true)='on' OR OLD.sent_at IS NULL THEN RETURN OLD; END IF;
    RAISE EXCEPTION 'sent admission decision is retained';
  END IF;
  IF OLD.sent_at IS NOT NULL AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)
    THEN RAISE EXCEPTION 'sent admission decision is immutable'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_applicationdecision_programme_sent BEFORE UPDATE OR DELETE ON events_applicationdecision FOR EACH ROW EXECUTE FUNCTION events_programme_sent_decision_guard();
CREATE FUNCTION events_programme_broadcast_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.confirmed_preview_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events_eventbroadcastpreview
    WHERE id=NEW.confirmed_preview_id AND campaign_id=NEW.id) THEN RAISE EXCEPTION 'broadcast preview campaign mismatch'; END IF;
  IF TG_OP='UPDATE' AND OLD.render_schema_version=2 THEN
    IF (NEW.event_id,NEW.makerspace_id,NEW.subject,NEW.body,NEW.render_schema_version,NEW.design,NEW.statuses,NEW.attendance)
      IS DISTINCT FROM (OLD.event_id,OLD.makerspace_id,OLD.subject,OLD.body,OLD.render_schema_version,OLD.design,OLD.statuses,OLD.attendance)
      OR (NEW.created_by_id IS NOT NULL AND NEW.created_by_id IS DISTINCT FROM OLD.created_by_id)
      THEN RAISE EXCEPTION 'confirmed composer content/sender is immutable'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventbroadcast_programme_composer BEFORE INSERT OR UPDATE ON events_eventbroadcast FOR EACH ROW EXECUTE FUNCTION events_programme_broadcast_guard();
CREATE FUNCTION events_programme_derivation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner_id bigint; prior_history jsonb;
BEGIN
  IF TG_OP='DELETE' THEN
    IF OLD.locked_at IS NOT NULL AND current_setting('app.allow_immutable_delete',true) IS DISTINCT FROM 'on'
      THEN RAISE EXCEPTION 'locked DOB source is retained'; END IF;
    RETURN OLD;
  END IF;
  SELECT COALESCE(r.member_id,a.member_id,c.member_id) INTO owner_id
    FROM (SELECT 1) seed LEFT JOIN events_eventregistration r ON r.id=NEW.registration_id
    LEFT JOIN events_hackathonapplication a ON a.id=NEW.application_id
    LEFT JOIN events_eventroleassignment c ON c.id=NEW.role_assignment_id;
  IF owner_id IS NOT NULL THEN PERFORM pii_assert_account_write_allowed(owner_id); END IF;
  IF NEW.source_dob_envelope !~ '^pii:gcm:v1:[1-9][0-9]*:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+$'
    OR jsonb_typeof(NEW.source_history)<>'array' THEN RAISE EXCEPTION 'DOB source requires typed encrypted evidence'; END IF;
  IF TG_OP='UPDATE' THEN
    IF (NEW.event_id,NEW.registration_id,NEW.application_id,NEW.role_assignment_id,NEW.question_id)
      IS DISTINCT FROM (OLD.event_id,OLD.registration_id,OLD.application_id,OLD.role_assignment_id,OLD.question_id)
      OR NEW.version<OLD.version THEN RAISE EXCEPTION 'DOB source binding is immutable'; END IF;
    SELECT COALESCE(jsonb_agg(value ORDER BY ord),'[]'::jsonb) INTO prior_history
      FROM jsonb_array_elements(NEW.source_history) WITH ORDINALITY x(value,ord)
      WHERE ord<=jsonb_array_length(OLD.source_history);
    IF prior_history IS DISTINCT FROM OLD.source_history THEN RAISE EXCEPTION 'DOB history is append-only'; END IF;
    IF OLD.locked_at IS NOT NULL AND (NEW.source_dob_envelope,NEW.as_of_date,NEW.event_date_revision,NEW.locked_at)
      IS DISTINCT FROM (OLD.source_dob_envelope,OLD.as_of_date,OLD.event_date_revision,OLD.locked_at)
      AND NOT (NEW.locked_at IS NULL AND jsonb_array_length(NEW.source_history)=jsonb_array_length(OLD.source_history)+1
        AND NEW.source_history -> -1 ->> 'source_dob_envelope'=OLD.source_dob_envelope
        AND (NEW.source_history -> -1 ->> 'version')::integer=OLD.version)
      THEN RAISE EXCEPTION 'reopen must archive locked DOB source'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER events_eventanswerderivation_programme_source BEFORE INSERT OR UPDATE OR DELETE ON events_eventanswerderivation FOR EACH ROW EXECUTE FUNCTION events_programme_derivation_guard();
"""

REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS events_eventanswerderivation_programme_source ON events_eventanswerderivation;
DROP TRIGGER IF EXISTS events_eventbroadcast_programme_composer ON events_eventbroadcast;
DROP TRIGGER IF EXISTS events_applicationdecision_programme_sent ON events_applicationdecision;
DROP TRIGGER IF EXISTS events_badgeprintresource_programme_bound ON events_badgeprintresource;
DROP TRIGGER IF EXISTS events_eventcertificatelibraryartwork_programme_promoted ON events_eventcertificatelibraryartwork;
DROP TRIGGER IF EXISTS events_eventcertificatelibrarycommand_programme_completion ON events_eventcertificatelibrarycommand;
DROP TRIGGER IF EXISTS events_galleryentrylink_programme_snapshot ON events_galleryentrylink;
DROP TRIGGER IF EXISTS events_galleryentryasset_programme_snapshot ON events_galleryentryasset;
DROP TRIGGER IF EXISTS events_galleryconsent_programme_snapshot ON events_galleryconsent;
DROP TRIGGER IF EXISTS events_galleryentry_programme_selection ON events_galleryentry;
DROP TRIGGER IF EXISTS events_galleryconsentitem_programme_selection ON events_galleryconsentitem;
DROP TRIGGER IF EXISTS events_judgerankingchoice_programme_ballot ON events_judgerankingchoice;
DROP TRIGGER IF EXISTS events_judgescore_programme_submitted ON events_judgescore;
DROP TRIGGER IF EXISTS events_judgingcriterion_programme_freeze ON events_judgingcriterion;
DROP TRIGGER IF EXISTS events_judginground_programme_freeze ON events_judginground;
DROP TRIGGER IF EXISTS events_eventcommandreceipt_programme_completion ON events_eventcommandreceipt;
DROP TRIGGER IF EXISTS events_teamcomment_programme_pii_fence ON events_teamcomment;
DROP TRIGGER IF EXISTS events_officehourschange_programme_pii_fence ON events_officehourschange;
DROP TRIGGER IF EXISTS events_mentorroundlock_programme_pii_fence ON events_mentorroundlock;
DROP TRIGGER IF EXISTS events_mentorroundcheckin_programme_pii_fence ON events_mentorroundcheckin;
DROP TRIGGER IF EXISTS events_mentorprofile_programme_pii_fence ON events_mentorprofile;
DROP TRIGGER IF EXISTS events_mentorimportpreview_programme_pii_fence ON events_mentorimportpreview;
DROP TRIGGER IF EXISTS events_mentorconflict_programme_pii_fence ON events_mentorconflict;
DROP TRIGGER IF EXISTS events_judgingreason_programme_pii_fence ON events_judgingreason;
DROP TRIGGER IF EXISTS events_judgescore_programme_pii_fence ON events_judgescore;
DROP TRIGGER IF EXISTS events_hackathonapplicationanswerrevision_programme_pii_fence ON events_hackathonapplicationanswerrevision;
DROP TRIGGER IF EXISTS events_hackathonapplication_programme_pii_fence ON events_hackathonapplication;
DROP TRIGGER IF EXISTS events_eventshiftattendancecorrection_programme_pii_fence ON events_eventshiftattendancecorrection;
DROP TRIGGER IF EXISTS events_eventroleassignment_programme_pii_fence ON events_eventroleassignment;
DROP TRIGGER IF EXISTS events_eventroleanswerrevision_programme_pii_fence ON events_eventroleanswerrevision;
DROP TRIGGER IF EXISTS events_eventrequirementoverride_programme_pii_fence ON events_eventrequirementoverride;
DROP TRIGGER IF EXISTS events_eventhelprequest_programme_pii_fence ON events_eventhelprequest;
DROP TRIGGER IF EXISTS events_eventhelpcomment_programme_pii_fence ON events_eventhelpcomment;
DROP TRIGGER IF EXISTS events_eventhelpaction_programme_pii_fence ON events_eventhelpaction;
DROP TRIGGER IF EXISTS events_eventcontributionhoursentry_programme_pii_fence ON events_eventcontributionhoursentry;
DROP TRIGGER IF EXISTS events_eventattendancecertificate_programme_pii_fence ON events_eventattendancecertificate;
DROP TRIGGER IF EXISTS events_eventanswerderivation_programme_pii_fence ON events_eventanswerderivation;
DROP TRIGGER IF EXISTS events_applicationreview_programme_pii_fence ON events_applicationreview;
DROP TRIGGER IF EXISTS events_eventregistrationcredential_programme_generation ON events_eventregistrationcredential;
DROP TRIGGER IF EXISTS events_hackathonteammember_deferred_leader ON events_hackathonteammember;
DROP TRIGGER IF EXISTS events_hackathonteam_deferred_leader ON events_hackathonteam;
DROP TRIGGER IF EXISTS events_hackathonteammember_programme_member ON events_hackathonteammember;
DROP TRIGGER IF EXISTS events_hackathonapplication_programme_member ON events_hackathonapplication;
DROP TRIGGER IF EXISTS events_eventmemberpresentation_programme_source ON events_eventmemberpresentation;
DROP TRIGGER IF EXISTS events_participantsponsorresumeconsent_programme_asset ON events_participantsponsorresumeconsent;
DROP TRIGGER IF EXISTS events_eventattendancecertificate_programme_subject ON events_eventattendancecertificate;
DROP TRIGGER IF EXISTS events_snapshotprize_owner ON events_snapshotprize;
DROP TRIGGER IF EXISTS events_snapshottrack_owner ON events_snapshottrack;
DROP TRIGGER IF EXISTS events_snapshotlink_owner ON events_snapshotlink;
DROP TRIGGER IF EXISTS events_snapshotasset_owner ON events_snapshotasset;
DROP TRIGGER IF EXISTS events_hackathonparticipantasset_guard ON events_hackathonparticipantasset;
DROP TRIGGER IF EXISTS events_submissionasset_guard ON events_submissionasset;
DROP TRIGGER IF EXISTS events_snapshotprize_immutable ON events_snapshotprize;
DROP TRIGGER IF EXISTS events_snapshottrack_immutable ON events_snapshottrack;
DROP TRIGGER IF EXISTS events_snapshotlink_immutable ON events_snapshotlink;
DROP TRIGGER IF EXISTS events_snapshotasset_immutable ON events_snapshotasset;
DROP TRIGGER IF EXISTS events_submissionsnapshot_immutable ON events_submissionsnapshot;
DROP TRIGGER IF EXISTS events_hackathonsubmission_owner ON events_hackathonsubmission;
DROP TRIGGER IF EXISTS events_galleryentrylink_programme_history ON events_galleryentrylink;
DROP TRIGGER IF EXISTS events_galleryentryasset_programme_history ON events_galleryentryasset;
DROP TRIGGER IF EXISTS events_judgerankingballot_programme_history ON events_judgerankingballot;
DROP TRIGGER IF EXISTS events_eventpresentationcommand_programme_history ON events_eventpresentationcommand;
DROP TRIGGER IF EXISTS events_eventcredentialcommand_programme_history ON events_eventcredentialcommand;
DROP TRIGGER IF EXISTS events_eventbadgetemplaterevision_programme_history ON events_eventbadgetemplaterevision;
DROP TRIGGER IF EXISTS events_eventcertificatelibraryrevision_programme_history ON events_eventcertificatelibraryrevision;
DROP TRIGGER IF EXISTS events_eventbroadcastpreview_programme_history ON events_eventbroadcastpreview;
DROP TRIGGER IF EXISTS events_eventformrevision_programme_history ON events_eventformrevision;
DROP TRIGGER IF EXISTS events_galleryamendment_programme_history ON events_galleryamendment;
DROP TRIGGER IF EXISTS events_galleryconsentrevision_programme_history ON events_galleryconsentrevision;
DROP TRIGGER IF EXISTS events_sponsorresumeconsenthistory_programme_history ON events_sponsorresumeconsenthistory;
DROP TRIGGER IF EXISTS events_sponsorwinnerproposal_programme_history ON events_sponsorwinnerproposal;
DROP TRIGGER IF EXISTS events_resultannouncement_programme_history ON events_resultannouncement;
DROP TRIGGER IF EXISTS events_eventaward_programme_history ON events_eventaward;
DROP TRIGGER IF EXISTS events_eventresultround_programme_history ON events_eventresultround;
DROP TRIGGER IF EXISTS events_eventresultrevision_programme_history ON events_eventresultrevision;
DROP TRIGGER IF EXISTS events_judgerankingchoice_programme_history ON events_judgerankingchoice;
DROP TRIGGER IF EXISTS events_judgingreason_programme_history ON events_judgingreason;
DROP TRIGGER IF EXISTS events_mentorassignmentrun_programme_history ON events_mentorassignmentrun;
DROP TRIGGER IF EXISTS events_eventcontributoradmission_programme_history ON events_eventcontributoradmission;
DROP TRIGGER IF EXISTS events_eventrequirementoverride_programme_history ON events_eventrequirementoverride;
DROP TRIGGER IF EXISTS events_eventroleanswerrevision_programme_history ON events_eventroleanswerrevision;
DROP TRIGGER IF EXISTS events_officehourschange_programme_history ON events_officehourschange;
DROP TRIGGER IF EXISTS events_mentornomination_programme_history ON events_mentornomination;
DROP TRIGGER IF EXISTS events_mentorroundcheckin_programme_history ON events_mentorroundcheckin;
DROP TRIGGER IF EXISTS events_eventhelpcomment_programme_history ON events_eventhelpcomment;
DROP TRIGGER IF EXISTS events_eventhelpaction_programme_history ON events_eventhelpaction;
DROP TRIGGER IF EXISTS events_eventshiftattendancecorrection_programme_history ON events_eventshiftattendancecorrection;
DROP TRIGGER IF EXISTS events_eventcontributionhoursentry_programme_history ON events_eventcontributionhoursentry;
DROP TRIGGER IF EXISTS events_hackathonteamexception_programme_history ON events_hackathonteamexception;
DROP TRIGGER IF EXISTS events_teamcomment_programme_history ON events_teamcomment;
DROP TRIGGER IF EXISTS events_applicationreview_programme_history ON events_applicationreview;
DROP TRIGGER IF EXISTS events_hackathonapplicationanswerrevision_programme_history ON events_hackathonapplicationanswerrevision;
DROP TRIGGER IF EXISTS events_hackathoncocrevision_programme_history ON events_hackathoncocrevision;
DROP TRIGGER IF EXISTS events_submissionintegrityflag_programme_scope ON events_submissionintegrityflag;
DROP TRIGGER IF EXISTS events_snapshotprize_programme_scope ON events_snapshotprize;
DROP TRIGGER IF EXISTS events_snapshottrack_programme_scope ON events_snapshottrack;
DROP TRIGGER IF EXISTS events_snapshotlink_programme_scope ON events_snapshotlink;
DROP TRIGGER IF EXISTS events_snapshotasset_programme_scope ON events_snapshotasset;
DROP TRIGGER IF EXISTS events_submissionlink_programme_scope ON events_submissionlink;
DROP TRIGGER IF EXISTS events_submissionsnapshot_programme_scope ON events_submissionsnapshot;
DROP TRIGGER IF EXISTS events_hackathonsubmission_programme_scope ON events_hackathonsubmission;
DROP TRIGGER IF EXISTS events_submissionassetwork_programme_scope ON events_submissionassetwork;
DROP TRIGGER IF EXISTS events_hackathonparticipantasset_programme_scope ON events_hackathonparticipantasset;
DROP TRIGGER IF EXISTS events_submissionasset_programme_scope ON events_submissionasset;
DROP TRIGGER IF EXISTS events_galleryamendment_programme_scope ON events_galleryamendment;
DROP TRIGGER IF EXISTS events_galleryentrylink_programme_scope ON events_galleryentrylink;
DROP TRIGGER IF EXISTS events_galleryentryasset_programme_scope ON events_galleryentryasset;
DROP TRIGGER IF EXISTS events_galleryentry_programme_scope ON events_galleryentry;
DROP TRIGGER IF EXISTS events_gallerypublication_programme_scope ON events_gallerypublication;
DROP TRIGGER IF EXISTS events_galleryconsentrevision_programme_scope ON events_galleryconsentrevision;
DROP TRIGGER IF EXISTS events_galleryconsentitem_programme_scope ON events_galleryconsentitem;
DROP TRIGGER IF EXISTS events_galleryconsent_programme_scope ON events_galleryconsent;
DROP TRIGGER IF EXISTS events_eventpresentationcommand_programme_scope ON events_eventpresentationcommand;
DROP TRIGGER IF EXISTS events_eventmembercard_programme_scope ON events_eventmembercard;
DROP TRIGGER IF EXISTS events_eventmemberpresentation_programme_scope ON events_eventmemberpresentation;
DROP TRIGGER IF EXISTS events_mentornotificationintent_programme_scope ON events_mentornotificationintent;
DROP TRIGGER IF EXISTS events_mentorimportpreview_programme_scope ON events_mentorimportpreview;
DROP TRIGGER IF EXISTS events_mentornomination_programme_scope ON events_mentornomination;
DROP TRIGGER IF EXISTS events_mentorconflict_programme_scope ON events_mentorconflict;
DROP TRIGGER IF EXISTS events_mentorroundcheckin_programme_scope ON events_mentorroundcheckin;
DROP TRIGGER IF EXISTS events_mentorroundlock_programme_scope ON events_mentorroundlock;
DROP TRIGGER IF EXISTS events_mentorround_programme_scope ON events_mentorround;
DROP TRIGGER IF EXISTS events_officehourschange_programme_scope ON events_officehourschange;
DROP TRIGGER IF EXISTS events_officehoursbooking_programme_scope ON events_officehoursbooking;
DROP TRIGGER IF EXISTS events_eventhelpcomment_programme_scope ON events_eventhelpcomment;
DROP TRIGGER IF EXISTS events_eventhelpaction_programme_scope ON events_eventhelpaction;
DROP TRIGGER IF EXISTS events_eventhelprequest_programme_scope ON events_eventhelprequest;
DROP TRIGGER IF EXISTS events_eventhelptype_programme_scope ON events_eventhelptype;
DROP TRIGGER IF EXISTS events_mentorteamassignment_programme_scope ON events_mentorteamassignment;
DROP TRIGGER IF EXISTS events_mentorprofile_programme_scope ON events_mentorprofile;
DROP TRIGGER IF EXISTS events_mentorattentionpreference_programme_scope ON events_mentorattentionpreference;
DROP TRIGGER IF EXISTS events_mentorassignmentrun_programme_scope ON events_mentorassignmentrun;
DROP TRIGGER IF EXISTS events_judgeconflict_programme_scope ON events_judgeconflict;
DROP TRIGGER IF EXISTS events_judgerankingchoice_programme_scope ON events_judgerankingchoice;
DROP TRIGGER IF EXISTS events_judgerankingballot_programme_scope ON events_judgerankingballot;
DROP TRIGGER IF EXISTS events_judgescore_programme_scope ON events_judgescore;
DROP TRIGGER IF EXISTS events_judgingroundproject_programme_scope ON events_judgingroundproject;
DROP TRIGGER IF EXISTS events_judgeassignment_programme_scope ON events_judgeassignment;
DROP TRIGGER IF EXISTS events_judgingreason_programme_scope ON events_judgingreason;
DROP TRIGGER IF EXISTS events_sponsorwinnerproposal_programme_scope ON events_sponsorwinnerproposal;
DROP TRIGGER IF EXISTS events_resultpublicationstate_programme_scope ON events_resultpublicationstate;
DROP TRIGGER IF EXISTS events_resultannouncement_programme_scope ON events_resultannouncement;
DROP TRIGGER IF EXISTS events_eventaward_programme_scope ON events_eventaward;
DROP TRIGGER IF EXISTS events_eventresultround_programme_scope ON events_eventresultround;
DROP TRIGGER IF EXISTS events_eventresultrevision_programme_scope ON events_eventresultrevision;
DROP TRIGGER IF EXISTS events_judgingcriterion_programme_scope ON events_judgingcriterion;
DROP TRIGGER IF EXISTS events_judginground_programme_scope ON events_judginground;
DROP TRIGGER IF EXISTS events_hackathonprize_programme_scope ON events_hackathonprize;
DROP TRIGGER IF EXISTS events_sponsorresumeconsenthistory_programme_scope ON events_sponsorresumeconsenthistory;
DROP TRIGGER IF EXISTS events_participantsponsorresumeconsent_programme_scope ON events_participantsponsorresumeconsent;
DROP TRIGGER IF EXISTS events_hackathonteamexception_programme_scope ON events_hackathonteamexception;
DROP TRIGGER IF EXISTS events_teamcomment_programme_scope ON events_teamcomment;
DROP TRIGGER IF EXISTS events_hackathonfinderprofile_programme_scope ON events_hackathonfinderprofile;
DROP TRIGGER IF EXISTS events_hackathonteaminvite_programme_scope ON events_hackathonteaminvite;
DROP TRIGGER IF EXISTS events_hackathonteammember_programme_scope ON events_hackathonteammember;
DROP TRIGGER IF EXISTS events_hackathonteam_programme_scope ON events_hackathonteam;
DROP TRIGGER IF EXISTS events_applicationdecision_programme_scope ON events_applicationdecision;
DROP TRIGGER IF EXISTS events_applicationreviewconflict_programme_scope ON events_applicationreviewconflict;
DROP TRIGGER IF EXISTS events_applicationreview_programme_scope ON events_applicationreview;
DROP TRIGGER IF EXISTS events_applicationreviewassignment_programme_scope ON events_applicationreviewassignment;
DROP TRIGGER IF EXISTS events_hackathonapplicationanswerrevision_programme_scope ON events_hackathonapplicationanswerrevision;
DROP TRIGGER IF EXISTS events_hackathonapplication_programme_scope ON events_hackathonapplication;
DROP TRIGGER IF EXISTS events_hackathonapplicationcohort_programme_scope ON events_hackathonapplicationcohort;
DROP TRIGGER IF EXISTS events_hackathonconfig_programme_scope ON events_hackathonconfig;
DROP TRIGGER IF EXISTS events_eventregistrationcredential_programme_scope ON events_eventregistrationcredential;
DROP TRIGGER IF EXISTS events_eventshiftattendancecorrection_programme_scope ON events_eventshiftattendancecorrection;
DROP TRIGGER IF EXISTS events_eventcontributionhoursentry_programme_scope ON events_eventcontributionhoursentry;
DROP TRIGGER IF EXISTS events_eventcontributionhours_programme_scope ON events_eventcontributionhours;
DROP TRIGGER IF EXISTS events_eventshiftattendance_programme_scope ON events_eventshiftattendance;
DROP TRIGGER IF EXISTS events_eventshiftsignup_programme_scope ON events_eventshiftsignup;
DROP TRIGGER IF EXISTS events_eventshift_programme_scope ON events_eventshift;
DROP TRIGGER IF EXISTS events_eventsponsortrack_programme_scope ON events_eventsponsortrack;
DROP TRIGGER IF EXISTS events_eventsponsor_programme_scope ON events_eventsponsor;
DROP TRIGGER IF EXISTS events_eventgrantentitlement_programme_scope ON events_eventgrantentitlement;
DROP TRIGGER IF EXISTS events_eventroleassignment_programme_scope ON events_eventroleassignment;
DROP TRIGGER IF EXISTS events_eventroleposting_programme_scope ON events_eventroleposting;
DROP TRIGGER IF EXISTS events_eventrequirementoverride_programme_scope ON events_eventrequirementoverride;
DROP TRIGGER IF EXISTS events_eventroleanswerrevision_programme_scope ON events_eventroleanswerrevision;
DROP TRIGGER IF EXISTS events_eventcontributornotice_programme_scope ON events_eventcontributornotice;
DROP TRIGGER IF EXISTS events_eventcontributoradmission_programme_scope ON events_eventcontributoradmission;
DROP TRIGGER IF EXISTS events_badgeprintresource_programme_scope ON events_badgeprintresource;
DROP TRIGGER IF EXISTS events_badgeprintjob_programme_scope ON events_badgeprintjob;
DROP TRIGGER IF EXISTS events_certificateissuebatchitem_programme_scope ON events_certificateissuebatchitem;
DROP TRIGGER IF EXISTS events_eventanswerderivation_programme_scope ON events_eventanswerderivation;
DROP TRIGGER IF EXISTS events_eventbroadcastpreview_programme_scope ON events_eventbroadcastpreview;
DROP FUNCTION IF EXISTS events_eventbroadcastpreview_scope_guard();
DROP FUNCTION IF EXISTS events_eventanswerderivation_scope_guard();
DROP FUNCTION IF EXISTS events_certificateissuebatchitem_scope_guard();
DROP FUNCTION IF EXISTS events_badgeprintjob_scope_guard();
DROP FUNCTION IF EXISTS events_badgeprintresource_scope_guard();
DROP FUNCTION IF EXISTS events_eventcontributoradmission_scope_guard();
DROP FUNCTION IF EXISTS events_eventcontributornotice_scope_guard();
DROP FUNCTION IF EXISTS events_eventroleanswerrevision_scope_guard();
DROP FUNCTION IF EXISTS events_eventrequirementoverride_scope_guard();
DROP FUNCTION IF EXISTS events_eventroleposting_scope_guard();
DROP FUNCTION IF EXISTS events_eventroleassignment_scope_guard();
DROP FUNCTION IF EXISTS events_eventgrantentitlement_scope_guard();
DROP FUNCTION IF EXISTS events_eventsponsor_scope_guard();
DROP FUNCTION IF EXISTS events_eventsponsortrack_scope_guard();
DROP FUNCTION IF EXISTS events_eventshift_scope_guard();
DROP FUNCTION IF EXISTS events_eventshiftsignup_scope_guard();
DROP FUNCTION IF EXISTS events_eventshiftattendance_scope_guard();
DROP FUNCTION IF EXISTS events_eventcontributionhours_scope_guard();
DROP FUNCTION IF EXISTS events_eventcontributionhoursentry_scope_guard();
DROP FUNCTION IF EXISTS events_eventshiftattendancecorrection_scope_guard();
DROP FUNCTION IF EXISTS events_eventregistrationcredential_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonconfig_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonapplicationcohort_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonapplication_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonapplicationanswerrevision_scope_guard();
DROP FUNCTION IF EXISTS events_applicationreviewassignment_scope_guard();
DROP FUNCTION IF EXISTS events_applicationreview_scope_guard();
DROP FUNCTION IF EXISTS events_applicationreviewconflict_scope_guard();
DROP FUNCTION IF EXISTS events_applicationdecision_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonteam_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonteammember_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonteaminvite_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonfinderprofile_scope_guard();
DROP FUNCTION IF EXISTS events_teamcomment_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonteamexception_scope_guard();
DROP FUNCTION IF EXISTS events_participantsponsorresumeconsent_scope_guard();
DROP FUNCTION IF EXISTS events_sponsorresumeconsenthistory_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonprize_scope_guard();
DROP FUNCTION IF EXISTS events_judginground_scope_guard();
DROP FUNCTION IF EXISTS events_judgingcriterion_scope_guard();
DROP FUNCTION IF EXISTS events_eventresultrevision_scope_guard();
DROP FUNCTION IF EXISTS events_eventresultround_scope_guard();
DROP FUNCTION IF EXISTS events_eventaward_scope_guard();
DROP FUNCTION IF EXISTS events_resultannouncement_scope_guard();
DROP FUNCTION IF EXISTS events_resultpublicationstate_scope_guard();
DROP FUNCTION IF EXISTS events_sponsorwinnerproposal_scope_guard();
DROP FUNCTION IF EXISTS events_judgingreason_scope_guard();
DROP FUNCTION IF EXISTS events_judgeassignment_scope_guard();
DROP FUNCTION IF EXISTS events_judgingroundproject_scope_guard();
DROP FUNCTION IF EXISTS events_judgescore_scope_guard();
DROP FUNCTION IF EXISTS events_judgerankingballot_scope_guard();
DROP FUNCTION IF EXISTS events_judgerankingchoice_scope_guard();
DROP FUNCTION IF EXISTS events_judgeconflict_scope_guard();
DROP FUNCTION IF EXISTS events_mentorassignmentrun_scope_guard();
DROP FUNCTION IF EXISTS events_mentorattentionpreference_scope_guard();
DROP FUNCTION IF EXISTS events_mentorprofile_scope_guard();
DROP FUNCTION IF EXISTS events_mentorteamassignment_scope_guard();
DROP FUNCTION IF EXISTS events_eventhelptype_scope_guard();
DROP FUNCTION IF EXISTS events_eventhelprequest_scope_guard();
DROP FUNCTION IF EXISTS events_eventhelpaction_scope_guard();
DROP FUNCTION IF EXISTS events_eventhelpcomment_scope_guard();
DROP FUNCTION IF EXISTS events_officehoursbooking_scope_guard();
DROP FUNCTION IF EXISTS events_officehourschange_scope_guard();
DROP FUNCTION IF EXISTS events_mentorround_scope_guard();
DROP FUNCTION IF EXISTS events_mentorroundlock_scope_guard();
DROP FUNCTION IF EXISTS events_mentorroundcheckin_scope_guard();
DROP FUNCTION IF EXISTS events_mentorconflict_scope_guard();
DROP FUNCTION IF EXISTS events_mentornomination_scope_guard();
DROP FUNCTION IF EXISTS events_mentorimportpreview_scope_guard();
DROP FUNCTION IF EXISTS events_mentornotificationintent_scope_guard();
DROP FUNCTION IF EXISTS events_eventmemberpresentation_scope_guard();
DROP FUNCTION IF EXISTS events_eventmembercard_scope_guard();
DROP FUNCTION IF EXISTS events_eventpresentationcommand_scope_guard();
DROP FUNCTION IF EXISTS events_galleryconsent_scope_guard();
DROP FUNCTION IF EXISTS events_galleryconsentitem_scope_guard();
DROP FUNCTION IF EXISTS events_galleryconsentrevision_scope_guard();
DROP FUNCTION IF EXISTS events_gallerypublication_scope_guard();
DROP FUNCTION IF EXISTS events_galleryentry_scope_guard();
DROP FUNCTION IF EXISTS events_galleryentryasset_scope_guard();
DROP FUNCTION IF EXISTS events_galleryentrylink_scope_guard();
DROP FUNCTION IF EXISTS events_galleryamendment_scope_guard();
DROP FUNCTION IF EXISTS events_submissionasset_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonparticipantasset_scope_guard();
DROP FUNCTION IF EXISTS events_submissionassetwork_scope_guard();
DROP FUNCTION IF EXISTS events_hackathonsubmission_scope_guard();
DROP FUNCTION IF EXISTS events_submissionsnapshot_scope_guard();
DROP FUNCTION IF EXISTS events_submissionlink_scope_guard();
DROP FUNCTION IF EXISTS events_snapshotasset_scope_guard();
DROP FUNCTION IF EXISTS events_snapshotlink_scope_guard();
DROP FUNCTION IF EXISTS events_snapshottrack_scope_guard();
DROP FUNCTION IF EXISTS events_snapshotprize_scope_guard();
DROP FUNCTION IF EXISTS events_submissionintegrityflag_scope_guard();
DROP FUNCTION IF EXISTS events_hackathoncocrevision_history_guard();
DROP FUNCTION IF EXISTS events_hackathonapplicationanswerrevision_history_guard();
DROP FUNCTION IF EXISTS events_applicationreview_history_guard();
DROP FUNCTION IF EXISTS events_teamcomment_history_guard();
DROP FUNCTION IF EXISTS events_hackathonteamexception_history_guard();
DROP FUNCTION IF EXISTS events_eventcontributionhoursentry_history_guard();
DROP FUNCTION IF EXISTS events_eventshiftattendancecorrection_history_guard();
DROP FUNCTION IF EXISTS events_eventhelpaction_history_guard();
DROP FUNCTION IF EXISTS events_eventhelpcomment_history_guard();
DROP FUNCTION IF EXISTS events_mentorroundcheckin_history_guard();
DROP FUNCTION IF EXISTS events_mentornomination_history_guard();
DROP FUNCTION IF EXISTS events_officehourschange_history_guard();
DROP FUNCTION IF EXISTS events_eventroleanswerrevision_history_guard();
DROP FUNCTION IF EXISTS events_eventrequirementoverride_history_guard();
DROP FUNCTION IF EXISTS events_eventcontributoradmission_history_guard();
DROP FUNCTION IF EXISTS events_mentorassignmentrun_history_guard();
DROP FUNCTION IF EXISTS events_judgingreason_history_guard();
DROP FUNCTION IF EXISTS events_judgerankingchoice_history_guard();
DROP FUNCTION IF EXISTS events_eventresultrevision_history_guard();
DROP FUNCTION IF EXISTS events_eventresultround_history_guard();
DROP FUNCTION IF EXISTS events_eventaward_history_guard();
DROP FUNCTION IF EXISTS events_resultannouncement_history_guard();
DROP FUNCTION IF EXISTS events_sponsorwinnerproposal_history_guard();
DROP FUNCTION IF EXISTS events_sponsorresumeconsenthistory_history_guard();
DROP FUNCTION IF EXISTS events_galleryconsentrevision_history_guard();
DROP FUNCTION IF EXISTS events_galleryamendment_history_guard();
DROP FUNCTION IF EXISTS events_eventformrevision_history_guard();
DROP FUNCTION IF EXISTS events_eventbroadcastpreview_history_guard();
DROP FUNCTION IF EXISTS events_eventcertificatelibraryrevision_history_guard();
DROP FUNCTION IF EXISTS events_eventbadgetemplaterevision_history_guard();
DROP FUNCTION IF EXISTS events_eventcredentialcommand_history_guard();
DROP FUNCTION IF EXISTS events_eventpresentationcommand_history_guard();
DROP FUNCTION IF EXISTS events_judgerankingballot_history_guard();
DROP FUNCTION IF EXISTS events_galleryentryasset_history_guard();
DROP FUNCTION IF EXISTS events_galleryentrylink_history_guard();
DROP FUNCTION IF EXISTS events_submission_immutable();
DROP FUNCTION IF EXISTS events_submission_asset_guard();
DROP FUNCTION IF EXISTS events_snapshot_reference_guard();
DROP FUNCTION IF EXISTS events_submission_project_guard();
DROP FUNCTION IF EXISTS events_programme_certificate_subject_guard();
DROP FUNCTION IF EXISTS events_programme_resume_consent_guard();
DROP FUNCTION IF EXISTS events_programme_presentation_guard();
DROP FUNCTION IF EXISTS events_programme_application_member_guard();
DROP FUNCTION IF EXISTS events_programme_team_member_guard();
DROP FUNCTION IF EXISTS events_programme_team_leader_guard();
DROP FUNCTION IF EXISTS events_programme_credential_guard();
CREATE OR REPLACE FUNCTION events_template_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'events_eventcertificatetemplaterevision' THEN
        IF NEW.artwork_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM events_eventcertificateartwork a
            WHERE a.id = NEW.artwork_id AND a.event_id = NEW.event_id AND a.promoted_at IS NOT NULL
        ) THEN RAISE EXCEPTION 'invalid certificate artwork ownership'; END IF;
    ELSE
        IF NEW.template_revision_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM events_eventcertificatetemplaterevision t
            JOIN events_eventregistration r ON r.event_id = t.event_id
            WHERE t.id = NEW.template_revision_id AND r.id = NEW.registration_id
        ) THEN RAISE EXCEPTION 'invalid certificate template ownership'; END IF;
    END IF;
    RETURN NEW;
END; $$;

DROP FUNCTION IF EXISTS events_applicationreview_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventanswerderivation_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventattendancecertificate_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventcontributionhoursentry_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventhelpaction_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventhelpcomment_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventhelprequest_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventrequirementoverride_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventroleanswerrevision_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventroleassignment_pii_fence_guard();
DROP FUNCTION IF EXISTS events_eventshiftattendancecorrection_pii_fence_guard();
DROP FUNCTION IF EXISTS events_hackathonapplication_pii_fence_guard();
DROP FUNCTION IF EXISTS events_hackathonapplicationanswerrevision_pii_fence_guard();
DROP FUNCTION IF EXISTS events_judgescore_pii_fence_guard();
DROP FUNCTION IF EXISTS events_judgingreason_pii_fence_guard();
DROP FUNCTION IF EXISTS events_mentorconflict_pii_fence_guard();
DROP FUNCTION IF EXISTS events_mentorimportpreview_pii_fence_guard();
DROP FUNCTION IF EXISTS events_mentorprofile_pii_fence_guard();
DROP FUNCTION IF EXISTS events_mentorroundcheckin_pii_fence_guard();
DROP FUNCTION IF EXISTS events_mentorroundlock_pii_fence_guard();
DROP FUNCTION IF EXISTS events_officehourschange_pii_fence_guard();
DROP FUNCTION IF EXISTS events_teamcomment_pii_fence_guard();
DROP FUNCTION IF EXISTS events_programme_receipt_guard();
DROP FUNCTION IF EXISTS events_programme_round_freeze();
DROP FUNCTION IF EXISTS events_programme_criterion_freeze();
DROP FUNCTION IF EXISTS events_programme_score_guard();
DROP FUNCTION IF EXISTS events_programme_rank_choice_guard();
DROP FUNCTION IF EXISTS events_programme_gallery_item_guard();
DROP FUNCTION IF EXISTS events_programme_gallery_entry_guard();
DROP FUNCTION IF EXISTS events_programme_gallery_consent_guard();
DROP FUNCTION IF EXISTS events_programme_gallery_reference_guard();
DROP FUNCTION IF EXISTS events_programme_library_command_guard();
DROP FUNCTION IF EXISTS events_programme_promoted_library_guard();
DROP FUNCTION IF EXISTS events_programme_print_resource_guard();
DROP FUNCTION IF EXISTS events_programme_sent_decision_guard();
DROP FUNCTION IF EXISTS events_programme_broadcast_guard();
DROP FUNCTION IF EXISTS events_programme_derivation_guard();
"""

class Migration(migrations.Migration):
    dependencies = [("events", "0043_events_programme_backfills"), ("encryption", "0009_account_programme_guards")]
    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
