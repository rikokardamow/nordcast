-- Layer #32 (docs/layers/residual-load): DK1 residual load = demand - wind -
-- solar, measured as thermal production + net import from the 5-min feed.
-- Consumption itself isn't added: the feed misses part of rooftop solar, so a
-- derived consumption runs up to ~700 MW low at summer midday (RISK.md).
insert into series (series_id, source_id, code, name, unit, frequency) values
    ('energinet.dk1.residual_load_mw', 'energinet',
     'ElectricityProdex5MinRealtime.ProductionLt100MW+ProductionGe100MW+Exchange*.DK1',
     'DK1 residual load (thermal production + net import = demand - wind - solar), ISP mean',
     'MW', '15min');
