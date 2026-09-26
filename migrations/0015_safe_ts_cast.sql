-- 0015: a cast of client-supplied ts text that can never raise.
-- The retention job used to guard the cast with a regex, but several strings pass that regex
-- and still make Postgres raise on the actual ::timestamptz cast (missing seconds before an
-- offset, an out-of-range offset, and so on). Because the retention job casts every org's rows
-- in one query, one such row from any org broke retention for every org. safe_ts replaces the
-- regex guard: it attempts the cast and returns NULL on any error, so it can never raise.
CREATE OR REPLACE FUNCTION safe_ts(t text) RETURNS timestamptz AS $$
BEGIN
    RETURN t::timestamptz;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
