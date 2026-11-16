"""Frozen SQL generator for typed v1 page tables (shared by schema migrations)."""


def sql(app, name):
    page = f"{app}_{name}"
    rev, asset = page + "revision", page + "asset"
    ra, rm = rev + "asset", rev + "member"
    owner = "makerspace_id" if app == "makerspaces" else "organization_id"
    return f"""
CREATE FUNCTION {page}_owner_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME='{asset}' OR to_jsonb(NEW)->'{owner}' IS DISTINCT FROM to_jsonb(OLD)->'{owner}' THEN
    RAISE EXCEPTION 'Page ownership and image metadata are immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER {page}_owner_guard BEFORE UPDATE ON {page}
FOR EACH ROW EXECUTE FUNCTION {page}_owner_guard();
CREATE TRIGGER {page}_owner_guard BEFORE UPDATE ON {asset}
FOR EACH ROW EXECUTE FUNCTION {page}_owner_guard();
CREATE FUNCTION {page}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_exists boolean;
BEGIN
  IF TG_OP='DELETE' AND current_setting('app.allow_immutable_delete', true)='on' THEN RETURN OLD; END IF;
  IF TG_TABLE_NAME='{rev}' THEN
    IF TG_OP='UPDATE' AND (to_jsonb(NEW)-'created_by_id')=(to_jsonb(OLD)-'created_by_id')
       AND NEW.created_by_id IS NULL THEN RETURN NEW; END IF;
    SELECT EXISTS(SELECT 1 FROM {page} WHERE id=OLD.page_id) INTO parent_exists;
  ELSE
    IF TG_TABLE_NAME='{rm}' AND TG_OP='UPDATE'
       AND (to_jsonb(NEW)-'profile_id')=(to_jsonb(OLD)-'profile_id')
       AND NEW.profile_id IS NULL THEN RETURN NEW; END IF;
    SELECT EXISTS(SELECT 1 FROM {rev} WHERE id=OLD.revision_id) INTO parent_exists;
  END IF;
  IF TG_OP='DELETE' AND NOT parent_exists THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'Page revisions and reference membership are immutable' USING ERRCODE='23514';
END $$;
CREATE TRIGGER {page}_immutable BEFORE UPDATE OR DELETE ON {rev}
FOR EACH ROW EXECUTE FUNCTION {page}_immutable();
CREATE TRIGGER {page}_immutable BEFORE UPDATE OR DELETE ON {ra}
FOR EACH ROW EXECUTE FUNCTION {page}_immutable();
CREATE TRIGGER {page}_immutable BEFORE UPDATE OR DELETE ON {rm}
FOR EACH ROW EXECUTE FUNCTION {page}_immutable();

CREATE FUNCTION {page}_final() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p {page}; r {rev}; rid uuid; expected jsonb; actual jsonb;
BEGIN
  IF TG_TABLE_NAME='{page}' THEN
    SELECT * INTO p FROM {page} WHERE id=NEW.id;
    IF NOT FOUND THEN RETURN NULL; END IF;
    IF (p.draft_revision_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM {rev} WHERE id=p.draft_revision_id AND page_id=p.id)) OR
       (p.published_revision_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM {rev} WHERE id=p.published_revision_id AND page_id=p.id)) OR
       (p.published_revision_id IS NOT NULL AND p.draft_revision_id IS NULL) THEN
      RAISE EXCEPTION 'Page pointers must reference their own revisions' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
  END IF;
  IF TG_TABLE_NAME='{rev}' THEN rid:=NEW.id; ELSE rid:=NEW.revision_id; END IF;
  SELECT * INTO r FROM {rev} WHERE id=rid;
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF r.schema_version<>1 THEN RAISE EXCEPTION 'Unsupported page snapshot version' USING ERRCODE='23514'; END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(r.document->'sections') s GROUP BY s->>'id' HAVING count(*)>1) THEN
    RAISE EXCEPTION 'Duplicate snapshot section slots' USING ERRCODE='23514';
  END IF;
  IF EXISTS (SELECT 1 FROM {ra} x JOIN {asset} a ON a.id=x.asset_id
             WHERE x.revision_id=rid AND a.page_id<>r.page_id) THEN
    RAISE EXCEPTION 'Revision asset belongs to another page' USING ERRCODE='23514';
  END IF;
  SELECT coalesce(jsonb_object_agg(slot, aid), '{{}}'::jsonb) INTO expected FROM (
    SELECT 'cover' AS slot, (r.document->>'cover_asset_id')::bigint AS aid
      WHERE r.document->>'cover_asset_id' IS NOT NULL
    UNION ALL
    SELECT (s->>'id')||':'||(ordinal-1)::text, (item->>'asset_id')::bigint
      FROM jsonb_array_elements(r.document->'sections') s,
      LATERAL jsonb_array_elements(s->'payload'->'items') WITH ORDINALITY x(item,ordinal)
      WHERE s->>'type'='gallery'
  ) slots;
  SELECT coalesce(jsonb_object_agg(slot, asset_id), '{{}}'::jsonb) INTO actual
    FROM {ra} WHERE revision_id=rid;
  IF expected<>actual THEN
    RAISE EXCEPTION 'Revision asset slots are incomplete' USING ERRCODE='23514';
  END IF;
  SELECT coalesce(jsonb_agg(slot ORDER BY slot), '[]'::jsonb) INTO expected FROM (
    SELECT item->>'member_slot_id' AS slot FROM jsonb_array_elements(r.document->'sections') s,
      LATERAL jsonb_array_elements(s->'payload'->'entries') item
      WHERE s->>'type'='team' AND item->>'kind'='member'
  ) slots;
  SELECT coalesce(jsonb_agg(slot::text ORDER BY slot::text), '[]'::jsonb) INTO actual
    FROM {rm} WHERE revision_id=rid;
  IF expected<>actual THEN
    RAISE EXCEPTION 'Revision member slots are incomplete' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
END $$;
""" + "\n".join(
        f"CREATE CONSTRAINT TRIGGER {page}_final AFTER INSERT OR UPDATE ON {table} "
        f"DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {page}_final();"
        for table in (page, rev, ra, rm)
    )


def reverse_sql(app, name):
    page = f"{app}_{name}"
    return ("\n".join(f"DROP TRIGGER {page}_final ON {table};" for table in
            (page, page + "revision", page + "revisionasset", page + "revisionmember"))
            + "\n" + "\n".join(f"DROP TRIGGER {page}_immutable ON {table};" for table in
            (page + "revision", page + "revisionasset", page + "revisionmember"))
            + f"\nDROP TRIGGER {page}_owner_guard ON {page}; DROP TRIGGER {page}_owner_guard ON {page}asset;"
            + f"\nDROP FUNCTION {page}_final(); DROP FUNCTION {page}_immutable(); DROP FUNCTION {page}_owner_guard();")
