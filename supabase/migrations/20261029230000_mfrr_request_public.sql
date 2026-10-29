-- mfrrRequest as it became public. The first series published each request at
-- its timeStamp, the moment it was issued to the AOF, up to ~20 minutes before
-- Energinet publishes it (7.5 min before the MTU starts, per the API guide):
-- a leak. Its rows stay (insert-only), superseded; nothing frozen ever read it.
insert into series (series_id, source_id, code, name, unit, frequency) values
    ('energinet.dk1.mfrr_request_public', 'energinet', 'mfrrRequest.DK1.public',
     'DK1 mFRR request to the AOF, each issue at the time it became public', 'MW', '15min');

update series set name = name || ' (superseded 29 Oct 2026: published at issue time, not publication; use energinet.dk1.mfrr_request_public)'
where series_id = 'energinet.dk1.mfrr_request';
