"""Frozen upgrade for the original page-history immutability functions."""


def immutable_sql(original, function, *, restore):
    start = original.index(f"CREATE FUNCTION {function}()")
    end = original.index("END $$;", start) + len("END $$;")
    statement = original[start:end].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    if not restore:
        return statement
    # The backup trigger runs first and proves active operation/component context
    # and exact staged old/new values. Do not admit the role without that guard.
    allowance = """AND (NEW.profile_id IS NULL OR (
         OLD.profile_id IS NULL AND current_user='spaceworks_b1_merge'
         AND EXISTS (SELECT 1 FROM pg_catalog.pg_trigger
           WHERE tgrelid=TG_RELID AND tgname='backup_b1_merge_write_guard'
             AND NOT tgisinternal AND tgenabled IN ('O', 'A')
             AND tgfoid=to_regprocedure('public.backup_b1_merge_write_guard()'))
       ))"""
    old = "AND NEW.profile_id IS NULL"
    if statement.count(old) != 1:
        raise ValueError("Expected exactly one frozen member-reference allowance")
    return statement.replace(old, allowance)
