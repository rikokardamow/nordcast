-- Where data comes from, and what we're allowed to show.
-- open: can go on any page. derived: only values we compute from it.
-- restricted: internal only, never reaches a page.
create table source (
    source_id     text primary key,
    name          text not null,
    licence_class text not null check (licence_class in ('open', 'derived', 'restricted')),
    licence       text not null,
    attribution   text not null,
    url           text,
    created_at    timestamptz not null default now()
);

-- One row per time series we pull. code is the source's own id for it.
create table series (
    series_id  text primary key,
    source_id  text not null references source (source_id),
    code       text not null,
    name       text not null,
    unit       text not null,
    frequency  text not null check (frequency in ('daily', 'weekly', 'monthly', 'quarterly', 'annual')),
    created_at timestamptz not null default now(),
    unique (source_id, code)
);

-- No policies yet, so the browser API can't read or write these.
-- The web role gets a filtered view later (stone 18).
alter table source enable row level security;
alter table series enable row level security;

insert into source (source_id, name, licence_class, licence, attribution, url) values
    ('eia', 'US Energy Information Administration', 'open',
     'US Government public domain', 'Source: U.S. EIA', 'https://www.eia.gov/opendata/');

insert into series (series_id, source_id, code, name, unit, frequency) values
    ('eia.wcestus1', 'eia', 'PET.WCESTUS1.W',
     'US commercial crude oil stocks excluding SPR', 'thousand barrels', 'weekly');
